def clean_logs(logs):
    # Remove extra spaces and empty lines
    lines = logs.split("\n")
    cleaned = [line.strip() for line in lines if line.strip()]
    
    return "\n".join(cleaned)