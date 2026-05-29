import os

path = r'd:\project\frontend\src\components\InsufficiencyList.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """                                    <div
                                        key={index}
                                        style={{
                                            width: '100%',
                                            minWidth: '1000px',
                                            borderBottom: '1px solid var(--border)',
                                            display: 'flex',
                                            alignItems: 'center',
                                            padding: '16px 24px',
                                            boxSizing: 'border-box',
                                            transition: 'background 0.1s',
                                            minHeight: '72px'
                                        }}
                                        className="cl-table-row"
                                    >"""

replacement = """                                    <div
                                        key={index}
                                        onClick={(e) => {
                                            if (e.target.closest('button')) return;
                                            const event = new CustomEvent('open-global-candidate-drawer', {
                                                detail: {
                                                    caseId: c.id,
                                                    caseRef: c.case_ref_no || '',
                                                    caseName: c.candidate_name || ''
                                                }
                                            });
                                            window.dispatchEvent(event);
                                        }}
                                        style={{
                                            width: '100%',
                                            minWidth: '1000px',
                                            borderBottom: '1px solid var(--border)',
                                            display: 'flex',
                                            alignItems: 'center',
                                            padding: '16px 24px',
                                            boxSizing: 'border-box',
                                            transition: 'background 0.1s',
                                            minHeight: '72px',
                                            cursor: 'pointer'
                                        }}
                                        className="cl-table-row"
                                    >"""

# Check Unix style
if target in content:
    content = content.replace(target, replacement)
    print("Replaced Unix style")
else:
    # Check Windows style
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
