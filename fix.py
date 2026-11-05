import re

with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

# The string we accidentally created is literal "${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'}"
# For line 106 it was already a template literal so it looks like `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'}/executions/${id}` (wait, line 106 was `${process...}`).

content = content.replace('"${process.env.NEXT_PUBLIC_API_URL || \'http://localhost:8000/api\'}/', '`${process.env.NEXT_PUBLIC_API_URL || \'http://localhost:8000/api\'}/')
content = content.replace('"${process.env.NEXT_PUBLIC_API_URL || \'http://localhost:8000/api\'}"', '`${process.env.NEXT_PUBLIC_API_URL || \'http://localhost:8000/api\'}`')

# Now fix the ending quote for the ones that had paths appended, e.g. `/github/analyze", {`
content = re.sub(r'(`\$\{process\.env\.NEXT_PUBLIC_API_URL \|\| \'http://localhost:8000/api\'\}[^\"]*)\"', r'\1`', content)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)
