import os

path = r'd:\project\frontend\src\components\NotificationsPage.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """                                                    if (isCustomer) {
                                                        navigate(`/candidates/${n.case_id}`);
                                                    } else {"""

replacement = """                                                    if (isCustomer) {
                                                        const event = new CustomEvent('open-global-candidate-drawer', {
                                                            detail: {
                                                                caseId: n.case_id,
                                                                caseRef: n.case_ref || '',
                                                                caseName: n.case_name || ''
                                                            }
                                                        });
                                                        window.dispatchEvent(event);
                                                    } else {"""

# Try Unix style
if target in content:
    content = content.replace(target, replacement)
    print("Replaced Unix style")
else:
    # Try Windows style
    target_win = target.replace('\n', '\r\n')
    replacement_win = replacement.replace('\n', '\r\n')
    if target_win in content:
        content = content.replace(target_win, replacement_win)
        print("Replaced Windows style")
    else:
        raise ValueError("Target not found in file content!")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Successfully wrote back file")
