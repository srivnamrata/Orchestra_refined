"""
Primary Orchestrator Agent
Coordinates all sub-agents and oversees workflow execution.
Manages the high-level strategy while delegating to specialists.
"""

import json
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging
from datetime import datetime
from backend.services.llm_utils import parse_llm_json
from backend.agents.workflow_schema import WorkflowPlan, WorkflowStep
from backend.api.routers.trace import emit_trace

logger = logging.getLogger(__name__)


@dataclass
class WorkflowRequest:
    """User request to execute a workflow"""
    request_id: str
    goal: str
    description: str
    priority: str  # "low", "medium", "high", "critical"
    deadline: Optional[str]
    context: Dict[str, Any]
    created_at: str


class OrchestratorAgent:
    """
    Primary Agent that:
    1. Understands user goals
    2. Breaks them into executable tasks
    3. Coordinates sub-agents (scheduler, task executor, knowledge agent)
    4. Manages the Critic agent feedback loop
    5. Ensures execution and provides progress updates
    """
    
    def __init__(self, llm_service, critic_agent, knowledge_graph, pubsub_service, event_bus=None):
        self.llm_service = llm_service
        self.critic_agent = critic_agent
        self.knowledge_graph = knowledge_graph
        self.pubsub = pubsub_service
        self.event_bus = event_bus
        self.workflows: Dict[str, Dict] = {}  # workflow_id -> workflow state
        self.sub_agents = {}  # Will be populated with scheduler, task, knowledge agents
    
    async def _think(self, agent: str, message: str, thought_type: str = "thought",
                     context_id: Optional[str] = None,
                     risk_level: Optional[str] = None):
        """Push a 'thinking' event to the reasoning queue AND the global thought bus."""
        event = {
            "type":    thought_type,
            "agent":   agent,
            "message": message,
            "context_id": context_id,
            "ts":      datetime.now().strftime("%H:%M:%S"),
        }
        if risk_level:
            event["risk_level"] = risk_level
        logger.info(f"[{agent}] {message}")
        
        if self.event_bus:
            role_map = {"orchestrator": "Orchestrator", "critic": "Critic Agent", "auditor": "Auditor", "knowledge": "Knowledge Agent"}
            await self.event_bus.publish("thought", {
                "agent": agent, "role": role_map.get(agent, agent.title()), 
                "message": message, "type": thought_type, 
                "context_id": context_id, "risk_level": risk_level
            })

        try:
            await emit_trace(agent, "thinking", message, {"context_id": context_id})
        except Exception as e:
            logger.error(f"Failed to emit live trace: {e}")

    def register_sub_agent(self, agent_type: str, agent_instance):
        """Register a sub-agent to be coordinated"""
        self.sub_agents[agent_type] = agent_instance
        logger.info(f"Registered sub-agent: {agent_type}")

    async def _subscribe_to_replan_events(self, workflow_id: str) -> None:
        """Listen for Critic-approved replans so in-flight workflows can adapt."""
        try:
            await self.pubsub.subscribe(
                topic=f"workflow-{workflow_id}-replan",
                callback=self._on_replan_message,
                context={"workflow_id": workflow_id},
            )
        except Exception as exc:
            logger.warning(f"Could not subscribe to replan events for {workflow_id}: {exc}")

    async def _on_replan_message(self, message: Dict[str, Any], context: Dict[str, Any]):
        """Forward a Critic-approved replan into the live workflow state."""
        workflow_id = context.get("workflow_id")
        if not workflow_id:
            return
        await self.handle_critic_replan(workflow_id, message)
    
    async def process_user_request(self, request: WorkflowRequest):
        """
        Main entry point: Process a user request and execute the workflow.
        Step 1: Understand goal
        Step 2: Generate execution plan
        Step 3: Build knowledge graph
        Step 4: Distribute to sub-agents
        Step 5: Monitor via Critic agent
        """
        from backend.database import save_workflow_state, update_workflow_state

        logger.info(f"🎯 Orchestrator processing request: {request.goal}")

        workflow_id = request.request_id
        self.workflows[workflow_id] = {
            "request": request,
            "status": "planning",
            "plan": None,
            "plan_schema_version": None,
            "plan_revision": 0,
            "replan_event": asyncio.Event(),
            "started_at": datetime.now().isoformat(),
        }
        save_workflow_state(workflow_id, request.goal, request.priority, "planning")

        try:
            # Step 1: Analyze the request and generate execution plan
            execution_plan = await self._generate_execution_plan(request)
            self.workflows[workflow_id]["plan"] = execution_plan
            self.workflows[workflow_id]["plan_schema_version"] = execution_plan.schema_version

            logger.info(f"✅ Generated execution plan for {workflow_id}")
            update_workflow_state(workflow_id, status="executing",
                                  plan_json=json.dumps(execution_plan.to_dict()))
            await self.pubsub.publish(f"workflow-{workflow_id}-status", {
                "status": "plan_ready",
                "steps": execution_plan.total_steps,
                "parallel_groups": len(execution_plan.parallel_groups),
            })

            # Step 2: Build knowledge graph from the plan
            await self._build_knowledge_graph(workflow_id, execution_plan)

            # Step 3: Start Critic agent monitoring — pass the original goal explicitly
            await self.critic_agent.start_monitoring(
                workflow_id,
                execution_plan.to_legacy_steps(),
                goal=request.goal,
            )
            await self._subscribe_to_replan_events(workflow_id)

            # Step 4: Execute the plan
            self.workflows[workflow_id]["status"] = "executing"
            await self._execute_plan(workflow_id, execution_plan)

        except Exception as e:
            logger.error(f"Error processing request {workflow_id}: {e}")
            self.workflows[workflow_id]["status"] = "failed"
            self.workflows[workflow_id]["error"] = str(e)
            update_workflow_state(workflow_id, status="failed", error=str(e))
            await self.pubsub.publish(f"workflow-{workflow_id}-status", {
                "status": "failed",
                "error": str(e),
            })
    
    async def _generate_execution_plan(self, request: WorkflowRequest) -> WorkflowPlan:
        """
        Use LLM to generate a detailed execution plan from user's goal.
        This is where we break down high-level goals into actionable steps.
        """
        prompt = f"""
        Goal: {request.goal}
        Description: {request.description}
        Priority: {request.priority}
        Deadline: {request.deadline}
        Context: {json.dumps(request.context)}
        
        Available Agents and their step types:
        - scheduler (type: calendar): For scheduling meetings and calendar events.
        - task (type: task): For creating, managing, and assigning tasks.
        - knowledge (type: search/note/integration): For fetching information, note taking, and integration.
        - analytics (type: analytics): For data analysis, generating reports, metrics, and charts.
        
        Generate a detailed execution plan in strict JSON format with the following structure:
        {{
            "goal": "...",
            "schema_version": "workflow-plan/v1",
            "total_steps": X,
            "steps": [
                {{
                    "step_id": 0,
                    "name": "step_name",
                    "type": "calendar|task|note|search|integration|analytics",
                    "agent": "scheduler|task|knowledge|analytics",
                    "depends_on": [step_ids],
                    "inputs": {{}},
                    "expected_outputs": [],
                    "error_handling": "retry|skip|escalate",
                    "timeout_seconds": 30
                }},
                ...
            ],
            "parallel_groups": [[0, 1], [2], [3, 4]],
            "estimated_duration_seconds": 300
        }}

        Rules:
        - step_id values must be explicit and unique.
        - depends_on must reference step_id values, not array positions.
        - parallel_groups should use step_id values and only group steps that can truly run together.
        - total_steps must match len(steps).
        """
        
        response = await self.llm_service.call(prompt)
        plan_json = parse_llm_json(response)
        plan = WorkflowPlan.from_payload(plan_json, default_goal=request.goal)

        if plan.normalization_warnings:
            for warning in plan.normalization_warnings:
                logger.warning(f"Plan normalization warning: {warning}")

        return plan
    
    async def _build_knowledge_graph(self, workflow_id: str, plan: WorkflowPlan):
        """
        Create nodes and edges in knowledge graph for this workflow.
        This gives the Critic agent context to understand the workflow.
        """
        # Create goal node
        goal_node_id = f"workflow-{workflow_id}-goal"
        await self.knowledge_graph.add_node(
            node_id=goal_node_id,
            node_type="goal",
            label=self.workflows[workflow_id]["request"].goal,
            attributes={
                "workflow_id": workflow_id,
                "priority": self.workflows[workflow_id]["request"].priority
            }
        )
        
        # Create task nodes and dependencies
        for step in plan.steps:
            step_id = f"workflow-{workflow_id}-step-{step.step_id}"
            
            await self.knowledge_graph.add_node(
                node_id=step_id,
                node_type="task",
                label=step.name,
                attributes={
                    "type": step.type,
                    "agent": step.agent,
                    "timeout": step.timeout_seconds,
                    "step_id": step.step_id,
                    "depends_on": list(step.depends_on),
                    "parallel_group": step.parallel_group,
                }
            )
            
            # Connect to goal
            await self.knowledge_graph.add_edge(
                source_id=step_id,
                target_id=goal_node_id,
                relationship_type="achieves"
            )
            
            # Connect dependencies
            for dep_id in step.depends_on:
                dep_step_id = f"workflow-{workflow_id}-step-{dep_id}"
                await self.knowledge_graph.add_edge(
                    source_id=step_id,
                    target_id=dep_step_id,
                    relationship_type="depends_on"
                )
        
        logger.info(f"Built knowledge graph for {workflow_id} with {len(plan.steps)} nodes")
    
    async def _execute_plan(self, workflow_id: str, plan: WorkflowPlan):
        """
        Execute the plan by delegating steps to appropriate sub-agents.
        Respects dependency constraints and runs parallel steps together.
        """
        workflow = self.workflows[workflow_id]
        completed_steps = set()
        pending_steps = plan.step_map()
        results: Dict[int, Any] = {}
        replan_event: asyncio.Event = workflow.setdefault("replan_event", asyncio.Event())
        active_plan = plan
        
        while pending_steps:
            if replan_event.is_set():
                active_plan = self._current_workflow_plan(workflow_id)
                pending_steps = {
                    step.step_id: step
                    for step in active_plan.steps
                    if step.step_id not in completed_steps
                }
                workflow["plan_revision"] = workflow.get("plan_revision", 0) + 1
                replan_event.clear()
                await self.pubsub.publish(f"workflow-{workflow_id}-status", {
                    "status": "replanning",
                    "plan_revision": workflow["plan_revision"],
                    "remaining_steps": len(pending_steps),
                })

            ready_batches = active_plan.ready_batches(tuple(completed_steps), tuple(pending_steps.keys()))
            if not ready_batches:
                # Deadlock detected - Critic agent should have caught this
                logger.error(f"Deadlock in workflow {workflow_id}")
                raise Exception("Circular dependency detected")
            
            for batch in ready_batches:
                execution_tasks = []
                for step in batch:
                    task = asyncio.create_task(
                        self._execute_step(workflow_id, step, results)
                    )
                    execution_tasks.append(task)

                batch_future = asyncio.ensure_future(
                    asyncio.gather(*execution_tasks, return_exceptions=True)
                )
                replan_wait = asyncio.create_task(replan_event.wait())

                done, _ = await asyncio.wait(
                    {batch_future, replan_wait},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if replan_wait in done:
                    logger.info(f"🔄 Replan requested mid-flight for {workflow_id}; interrupting current batch")
                    for task in execution_tasks:
                        task.cancel()
                    batch_results = await asyncio.gather(*execution_tasks, return_exceptions=True)
                    await asyncio.gather(batch_future, return_exceptions=True)
                    replan_wait.cancel()

                    for step, result in zip(batch, batch_results):
                        if not isinstance(result, BaseException):
                            results[step.step_id] = result
                            completed_steps.add(step.step_id)
                            pending_steps.pop(step.step_id, None)

                    active_plan = self._current_workflow_plan(workflow_id)
                    pending_steps = {
                        step.step_id: step
                        for step in active_plan.steps
                        if step.step_id not in completed_steps
                    }
                    workflow["plan_revision"] = workflow.get("plan_revision", 0) + 1
                    replan_event.clear()
                    await self.pubsub.publish(f"workflow-{workflow_id}-status", {
                        "status": "replanning",
                        "plan_revision": workflow["plan_revision"],
                        "remaining_steps": len(pending_steps),
                    })
                    break

                replan_wait.cancel()
                step_results = await batch_future

                # Process results
                for step, result in zip(batch, step_results):
                    if isinstance(result, BaseException):
                        logger.error(f"Step {step.step_id} failed: {result}")
                        if step.error_handling != "skip":
                            raise result
                    else:
                        results[step.step_id] = result
                        completed_steps.add(step.step_id)
                        pending_steps.pop(step.step_id, None)
        
        workflow["status"] = "completed"
        workflow["results"] = results
        logger.info(f"✅ Workflow {workflow_id} completed successfully")

        from backend.database import update_workflow_state
        # results values may not be JSON-serialisable; convert to strings as a safe fallback
        try:
            results_json = json.dumps(results)
        except (TypeError, ValueError):
            results_json = json.dumps({k: str(v) for k, v in results.items()})
        update_workflow_state(workflow_id, status="completed", results_json=results_json)

        await self.pubsub.publish(f"workflow-{workflow_id}-status", {
            "status": "completed",
            "results": results,
        })
    
    async def _execute_step(self, workflow_id: str, step: WorkflowStep, previous_results: Dict) -> Any:
        """
        Execute a single step using the appropriate sub-agent.
        """
        step_payload = step.to_dict()
        logger.info(f"Executing step {step.step_id}: {step.name}")
        
        await self._think("orchestrator", f"Executing step {step.step_id}: {step.name}", context_id=workflow_id)
        agent_type = step.agent
        if agent_type not in self.sub_agents:
            raise ValueError(f"No sub-agent of type '{agent_type}'")
        
        agent = self.sub_agents[agent_type]
        
        # Publish progress update
        await self.pubsub.publish(f"workflow-{workflow_id}-progress", {
            "workflow_id": workflow_id,
            "step_id": step.step_id,
            "step_name": step.name,
            "parallel_group": step.parallel_group,
            "status": "executing",
            "timestamp": datetime.now().isoformat()
        })
        
        step_started_at = datetime.now()
        try:
            # Execute step with timeout
            result = await asyncio.wait_for(
                agent.execute(step_payload, previous_results),
                timeout=step.timeout_seconds
            )

            duration = round((datetime.now() - step_started_at).total_seconds(), 2)

            # Publish completion with actual wall-clock duration
            await self.pubsub.publish(f"workflow-{workflow_id}-progress", {
                "workflow_id":      workflow_id,
                "step_id":          step.step_id,
                "step_name":        step.name,
                "parallel_group":   step.parallel_group,
                "status":           "completed",
                "duration_seconds": duration,
                "result_summary":   str(result)[:100],
            })
            
            return result
        
        except asyncio.TimeoutError:
            logger.error(f"Step {step.step_id} timed out")
            raise Exception(f"Step {step.step_id} timeout exceeded")
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow status — checks in-memory state first, then falls back to DB."""
        workflow = self.workflows.get(workflow_id)
        if workflow:
            plan = workflow.get("plan")
            plan_steps = len(plan.steps) if isinstance(plan, WorkflowPlan) else len(plan or [])
            return {
                "workflow_id": workflow_id,
                "status":      workflow.get("status"),
                "goal":        workflow.get("request").goal,
                "started_at":  workflow.get("started_at"),
                "plan_steps":  plan_steps,
                "plan_schema_version": workflow.get("plan_schema_version"),
                "critic_report": self.critic_agent.get_workflow_audit_report(workflow_id),
            }

        # Not in memory — try DB (handles post-restart or cross-instance lookups)
        from backend.database import get_workflow_state
        db_state = get_workflow_state(workflow_id)
        if not db_state:
            return {"error": "Workflow not found"}
        plan_payload = json.loads(db_state.plan_json) if db_state.plan_json else []
        plan = WorkflowPlan.from_payload(plan_payload)
        return {
            "workflow_id":   workflow_id,
            "status":        db_state.status,
            "goal":          db_state.goal,
            "started_at":    db_state.started_at.isoformat(),
            "plan_steps":    len(plan.steps),
            "plan_schema_version": plan.schema_version,
            "critic_report": self.critic_agent.get_workflow_audit_report(workflow_id),
            "source":        "database",
        }
    
    async def handle_critic_replan(self, workflow_id: str, replan_message: Dict):
        """
        Handle replan decision from Critic agent.
        This is the autonomous replanning feature in action.
        """
        logger.info(f"🔄 Handling replan for workflow {workflow_id}")
        
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return
        
        if replan_message.get("approved_by_critic"):
            logger.info(f"✅ Accepting Critic's replan suggestion")
            revised_plan = replan_message.get("revised_plan", [])
            revised_workflow_plan = WorkflowPlan.from_payload(
                revised_plan,
                default_goal=workflow["request"].goal,
            )
            workflow["plan"]   = revised_workflow_plan
            workflow["plan_schema_version"] = revised_workflow_plan.schema_version
            workflow["status"] = "replanned"
            replan_event = workflow.setdefault("replan_event", asyncio.Event())
            replan_event.set()

            from backend.database import update_workflow_state
            update_workflow_state(workflow_id, status="replanned",
                                  plan_json=json.dumps(revised_workflow_plan.to_dict()))

            await self.pubsub.publish(f"workflow-{workflow_id}-replan-accepted", {
                "reasoning":      replan_message.get("reasoning"),
                "efficiency_gain": replan_message.get("efficiency_gain"),
                "parallel_groups": len(revised_workflow_plan.parallel_groups),
                "risk_level": "low", # Indicate a successful replan has low risk
            })
        else:
            logger.warning(f"Replan rejected by Critic")

    def _current_workflow_plan(self, workflow_id: str) -> WorkflowPlan:
        """Return the most recent workflow plan for a workflow."""
        workflow = self.workflows.get(workflow_id, {})
        plan = workflow.get("plan")
        if isinstance(plan, WorkflowPlan):
            return plan
        goal = ""
        request = workflow.get("request")
        if request is not None:
            goal = getattr(request, "goal", "") or ""
        return WorkflowPlan.from_payload(plan or [], default_goal=goal)
