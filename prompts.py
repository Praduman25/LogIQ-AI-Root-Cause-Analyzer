def get_rca_prompt(logs):
    return f"""
You are an expert DevOps/SRE engineer specializing in root cause analysis.

Analyze the following logs and respond ONLY in this exact format with these exact section headers:

Severity:
High / Medium / Low

Confidence:
A percentage like 95%

Root Cause:
One clear, concise sentence describing the root cause.

Explanation:
2-4 sentences explaining what happened and why, in plain English.

Solution:
- Step 1 to fix the issue
- Step 2 to fix the issue
- Step 3 (if needed)

Prevention:
- How to prevent this in future
- Monitoring/alerting recommendations
- Best practices to follow

---
Logs to analyze:

{logs}

---
RULES:
- Follow the EXACT section order above
- Do NOT add any extra sections or markdown
- Keep Root Cause to a single sentence
- Write bullet points starting with a dash (-)
"""
