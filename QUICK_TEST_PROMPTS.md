# Quick Test Prompts for Cowork Agentic Workflow

Quick reference prompts for testing different aspects of your agentic system.

---

## 🚀 Basic Functionality

**Simple Task**:
```
Create a Python script that prints "Hello, Cowork!" and run it.
```

**File Operations**:
```
Create a file called test.txt with the content "This is a test" and then read it back to me.
```

**Web Search**:
```
Search the web for "AI agent frameworks" and summarize the top 3 results.
```

---

## 🔧 Tool Calling

**Multiple Tools**:
```
1. Search for "Python best practices"
2. Create a markdown file with the findings
3. Read the file and display it
```

**Terminal Operations**:
```
Create a simple bash script that lists all files in the current directory and saves the output to files.txt
```

**Browser Operations**:
```
Visit https://www.example.com and extract the page title and first paragraph.
```

---

## 🌐 Multi-Agent Workflows

**Task Decomposition**:
```
Build a web scraper that searches for "AI tools", extracts results, and creates a comparison table.
```

**Agent Collaboration**:
```
Research "Python web frameworks", create a comparison document, and generate a summary report.
```

**Complex Workflow**:
```
Analyze a GitHub repository: search for it, get details, analyze structure, and create a summary document.
```

---

## 📊 Real-World Scenarios

**Data Analysis**:
```
Fetch data from an API, process it, create visualizations, and generate a report.
```

**Code Generation**:
```
Create a Python REST API with FastAPI that has endpoints for CRUD operations on a todo list.
```

**Documentation**:
```
Create comprehensive documentation for a Python project including README, API docs, and examples.
```

**Web Development**:
```
Build a simple HTML page with CSS and JavaScript that displays a counter that increments on button click.
```

---

## ⚠️ Error Handling Tests

**Invalid File**:
```
Read a file that doesn't exist: /nonexistent/file.txt
```

**Invalid Command**:
```
Execute this invalid command: python nonexistent_script.py
```

**Network Error**:
```
Try to fetch data from an invalid URL: https://invalid-url-12345.com
```

---

## 🔐 Provider Validation

**Valid Provider**:
- Go to Settings → Providers
- Add OpenAI provider with valid API key
- Click "Validate"
- Should show: ✅ Valid, Tool calls supported

**Invalid Provider**:
- Add provider with invalid API key
- Click "Validate"
- Should show: ❌ Invalid API key error

---

## 🎯 Comprehensive Test

**Full Workflow**:
```
I'm building a Python web scraper. Help me:
1. Research best Python scraping libraries
2. Create project structure (requirements.txt, main.py, README.md)
3. Write a scraper that fetches webpage title and first paragraph
4. Test it with a sample URL
5. Create a summary document

Use appropriate agents and tools for each step.
```

---

## ✅ Quick Verification Checklist

After running a test, check:

- [ ] SSE events received (`confirmed`, `create_agent`, `assign_task`, `activate_toolkit`, `end`)
- [ ] Workflow diagram updates in real-time
- [ ] Tool calls appear in chat/logs
- [ ] Files created (if applicable)
- [ ] Task completes successfully
- [ ] Session saved to history
- [ ] No errors in console/logs

---

**Tip**: Start with simple tests, then progress to complex workflows. Monitor both frontend console and backend logs for issues.

