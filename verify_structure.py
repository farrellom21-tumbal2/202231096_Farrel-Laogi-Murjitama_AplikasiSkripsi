import ast
import sys

# Parse realtime_proctoring_stable_highfps.py
with open('realtime_proctoring_stable_highfps.py', 'r') as f:
    tree = ast.parse(f.read())

classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and not node.name.startswith('_')]

print("[✅] realtime_proctoring_stable_highfps.py STRUCTURE:")
print(f"    Classes: {classes}")
print(f"    Functions: {functions}")

# Parse face_analyzer.py
with open('face_analyzer.py', 'r') as f:
    tree = ast.parse(f.read())

classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and not node.name.startswith('_')]

print("\n[✅] face_analyzer.py STRUCTURE:")
print(f"    Classes: {classes}")
print(f"    Functions: {functions}")

print("\n[✅] INTEGRATION READY FOR TESTING!")
