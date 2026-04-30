with open('/Users/Shared/Orchestra_refined/frontend/app.js', 'r') as f:
    text = f.read()

lines = text.split('\n')
brace_stack = []
bracket_stack = []

for i, line in enumerate(lines):
    # ignore comments simply (not perfect, but enough)
    line = line.split('//')[0]
    for char in line:
        if char == '{':
            brace_stack.append(i+1)
        elif char == '}':
            if brace_stack:
                brace_stack.pop()
        elif char == '[':
            bracket_stack.append(i+1)
        elif char == ']':
            if bracket_stack:
                bracket_stack.pop()

print("Unclosed braces at lines:", brace_stack)
print("Unclosed brackets at lines:", bracket_stack)
