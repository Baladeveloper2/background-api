import sys
content = open('d:/project/backend/app/case_routes.py', encoding='utf-8').read()
new_routes = open('d:/project/backend/new_insufficiency_routes.py', encoding='utf-8').read()
target = '@router.get("/insufficiencies/{id}")'
new_content = content.replace(target, new_routes + '\n\n' + target)
open('d:/project/backend/app/case_routes.py', 'w', encoding='utf-8').write(new_content)
print("Injected successfully")
