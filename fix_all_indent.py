with open('hr_attendance.py', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

lines = content.split('\n')
fixed = []

for i, line in enumerate(lines):
    # Check for if statements that need indented blocks
    if line.strip().startswith('if ') and not line.strip().endswith(':'):
        # Check if next line is in if block
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line.strip() and not next_line.startswith('                ') and not next_line.startswith('            '):
                # Need to fix indentation
                if 'drop' in next_line or '=' in next_line:
                    lines[i + 1] = '                ' + next_line.lstrip()
                    continue
    fixed.append(line)

# Also fix specific problematic lines
for i in range(len(fixed)):
    line = fixed[i]
    # Lines that should be indented after if statements
    if i >= 320 and i < 350:
        if 'if ' in line and ':':
            continue
        if line.strip().startswith('df_fac_detail_ID.drop') and not line.startswith('                '):
            fixed[i] = '                ' + line.lstrip()
        if line.strip().startswith('df_admin_detail_ID.drop') and not line.startswith('                '):
            fixed[i] = '                ' + line.lstrip()
        if 'df_fac_conso_ID = pd.merge' in line and not line.startswith('            '):
            fixed[i] = '            ' + line.lstrip()
        if 'df_admin_conso_ID = pd.merge' in line and not line.startswith('            '):
            fixed[i] = '            ' + line.lstrip()
        if 'if \'Names\' in df_fac_conso_ID.columns:' in line and not line.startswith('                '):
            fixed[i] = '                ' + line.lstrip()
        if 'if \'Names\' in df_admin_conso_ID.columns:' in line and not line.startswith('                '):
            fixed[i] = '                ' + line.lstrip()
        if 'df_fac_conso_ID.drop' in line and not line.startswith('                    '):
            fixed[i] = '                    ' + line.lstrip()
        if 'df_admin_conso_ID.drop' in line and not line.startswith('                    '):
            fixed[i] = '                    ' + line.lstrip()

with open('hr_attendance.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(fixed))

print("Fixed all indentation")


