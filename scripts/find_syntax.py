import tokenize, io

path = r'autenticacion\autenticacion.py'
with open(path, 'r', encoding='utf-8') as f:
    all_lines = f.read().split('\n')

# Binary search for the exact line where error first appears
lo, hi = 1, 2526

while lo < hi:
    mid = (lo + hi) // 2
    partial = '\n'.join(all_lines[:mid])
    try:
        list(tokenize.generate_tokens(io.StringIO(partial).readline))
        lo = mid + 1  # OK up to mid, error is after
    except tokenize.TokenError:
        hi = mid      # Error starts at or before mid

print(f"Error first appears when including line {lo}")
# Show context
for i in range(max(0, lo-5), min(len(all_lines), lo+3)):
    marker = ">>>" if i+1 == lo else "   "
    print(f"{marker} {i+1}: {repr(all_lines[i])}")
