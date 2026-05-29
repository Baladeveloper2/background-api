import os

path = r'd:\project\frontend\src\components\CandidateInvitationList.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace corrupted character sequence 'â€”' with unicode escape '\u2014' or a clean dash '-'
# Let's use '\u2014' which displays as '—' safely
new_content = content.replace('â€”', '\\u2014')

if new_content != content:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully replaced all instances of 'â€”' with '\\u2014'")
else:
    print("No instances of 'â€”' found to replace!")
