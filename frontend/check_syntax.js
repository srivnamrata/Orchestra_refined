const fs = require('fs');
const content = fs.readFileSync('/Users/Shared/Orchestra_refined/frontend/app.js', 'utf8');
try {
  new Function(content);
} catch (e) {
  console.log(e.toString());
  // Unfortunately new Function doesn't give line numbers easily in osascript, wait, fs is node.
}
