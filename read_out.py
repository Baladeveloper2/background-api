
import os
with open('out.txt', 'rb') as f:
    content = f.read().decode('utf-16')
    print(content)
