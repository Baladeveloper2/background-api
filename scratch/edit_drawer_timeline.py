import os

path = r'd:\project\frontend\src\components\shared\CandidateDetailsDrawer.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Let's clean up the corrupted section first by searching for:
#         <Activity size={13} /> Verification Timeline Activity
#     </div>
# And replace it with the clean {!isCustomer && ...} version

target_corrupted = """                                        <Activity size={13} /> Verification Timeline Activity
                                    </div>"""

# Let's inspect the exact lines to match.
# In the previous view_file:
# 754:                                 </div>
# 755: 
# 756:                                         <Activity size={13} /> Verification Timeline Activity
# 757:                                     </div>
# 758:                                     {checkDetails.timeline && checkDetails.timeline.length > 0 ? (
# ...
# 790:                                             No timeline activity records.
# 791:                                         </div>
# 792:                                     )}
# 793:                                 </div>
# 794:                             </>

# So the target block to replace is from lines 756 to 793.
# Let's make a precise multiline block for search:

search_block = """                                        <Activity size={13} /> Verification Timeline Activity
                                    </div>
                                    {checkDetails.timeline && checkDetails.timeline.length > 0 ? (
                                        <ul className="audit-timeline">
                                            {checkDetails.timeline.map((step, sIdx) => (
                                                <li key={sIdx} className={`audit-item ${step.completed ? 'completed' : ''}`}>
                                                    <div className="audit-dot" />
                                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                                        <div>
                                                            <div style={{ fontSize: '12.5px', fontWeight: 600, color: step.completed ? '#111827' : '#6B7280' }}>
                                                                {step.stage}
                                                            </div>
                                                            <div style={{ fontSize: '11px', color: '#6B7280', marginTop: '1px' }}>
                                                                {step.remarks}
                                                            </div>
                                                        </div>
                                                        {step.timestamp && (
                                                            <div style={{ textAlign: 'right' }}>
                                                                <div style={{ fontSize: '11px', fontWeight: 500, color: '#111827' }}>
                                                                    {step.timestamp}
                                                                </div>
                                                                <div style={{ fontSize: '9.5px', color: '#6B7280', marginTop: '1px' }}>
                                                                    by {step.performer}
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <div style={{ padding: '16px', background: '#FAFAFA', borderRadius: '8px', border: '1px solid #E5E7EB', textAlign: 'center', fontSize: '12px', color: '#6B7280', fontWeight: 500 }}>
                                            No timeline activity records.
                                        </div>
                                    )}
                                </div>
                            </>"""

replacement_block = """                                {!isCustomer && (
                                    <div>
                                        <div className="detail-section-title">
                                            <Activity size={13} /> Verification Timeline Activity
                                        </div>
                                        {checkDetails.timeline && checkDetails.timeline.length > 0 ? (
                                            <ul className="audit-timeline">
                                                {checkDetails.timeline.map((step, sIdx) => (
                                                    <li key={sIdx} className={`audit-item ${step.completed ? 'completed' : ''}`}>
                                                        <div className="audit-dot" />
                                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                                            <div>
                                                                <div style={{ fontSize: '12.5px', fontWeight: 600, color: step.completed ? '#111827' : '#6B7280' }}>
                                                                    {step.stage}
                                                                </div>
                                                                <div style={{ fontSize: '11px', color: '#6B7280', marginTop: '1px' }}>
                                                                    {step.remarks}
                                                                </div>
                                                            </div>
                                                            {step.timestamp && (
                                                                <div style={{ textAlign: 'right' }}>
                                                                    <div style={{ fontSize: '11px', fontWeight: 500, color: '#111827' }}>
                                                                        {step.timestamp}
                                                                    </div>
                                                                    <div style={{ fontSize: '9.5px', color: '#6B7280', marginTop: '1px' }}>
                                                                        by {step.performer}
                                                                    </div>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </li>
                                                ))}
                                            </ul>
                                        ) : (
                                            <div style={{ padding: '16px', background: '#FAFAFA', borderRadius: '8px', border: '1px solid #E5E7EB', textAlign: 'center', fontSize: '12px', color: '#6B7280', fontWeight: 500 }}>
                                                No timeline activity records.
                                            </div>
                                        )}
                                    </div>
                                )}
                            </>"""

# Check Unix style
if search_block in content:
    content = content.replace(search_block, replacement_block)
    print("Replaced Unix style")
else:
    # Check Windows style
    search_block_win = search_block.replace('\n', '\r\n')
    replacement_block_win = replacement_block.replace('\n', '\r\n')
    if search_block_win in content:
        content = content.replace(search_block_win, replacement_block_win)
        print("Replaced Windows style")
    else:
        raise ValueError("Search block not found in file content!")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Successfully restored and updated CandidateDetailsDrawer.jsx")
