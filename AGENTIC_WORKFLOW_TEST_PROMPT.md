# Agentic Workflow Testing Prompt

Use this comprehensive prompt to test your Cowork agentic workflow end-to-end. Test each scenario systematically and verify all components are working correctly.

---

## 🎯 Test Scenario 1: Basic Agent Task Execution

**Objective**: Verify basic agent can receive, process, and respond to a simple task.

**Test Prompt**:
```
Create a simple Python script that prints "Hello, Cowork!" and saves it to a file called hello.py. Then execute it and show me the output.
```

**Expected Behavior**:
- ✅ Agent receives the task
- ✅ Task is decomposed into subtasks (if needed)
- ✅ Agent uses file_write tool to create hello.py
- ✅ Agent uses terminal/code_execution tool to run the script
- ✅ Output is streamed via SSE
- ✅ Task completes successfully
- ✅ File artifact is created and visible

**What to Check**:
- [ ] SSE events: `confirmed`, `create_agent`, `assign_task`, `activate_toolkit`, `deactivate_toolkit`, `end`
- [ ] Tool calls appear in workflow diagram
- [ ] File appears in artifacts/snapshots
- [ ] Task state transitions: waiting → running → done

---

## 🔧 Test Scenario 2: Tool Calling Validation

**Objective**: Verify agent can use multiple tools correctly.

**Test Prompt**:
```
1. Search the web for "Python best practices 2024"
2. Create a markdown file summarizing the top 3 practices
3. Read the file back and display its contents
```

**Expected Behavior**:
- ✅ Agent uses `search` or `browser` tool
- ✅ Agent uses `file_write` tool to create markdown file
- ✅ Agent uses `file` tool to read the file
- ✅ All tool calls are logged and visible
- ✅ Results are properly formatted

**What to Check**:
- [ ] Multiple `activate_toolkit`/`deactivate_toolkit` events
- [ ] Tool results appear in agent messages
- [ ] File is created with correct content
- [ ] No tool execution errors

---

## 🌐 Test Scenario 3: Multi-Agent Workflow

**Objective**: Verify task decomposition and multi-agent coordination.

**Test Prompt**:
```
Build a simple web scraper that:
1. Searches for "AI agent frameworks" 
2. Extracts the top 5 results
3. Creates a comparison table in markdown
4. Generates a summary report

Break this down into subtasks and use appropriate agents for each part.
```

**Expected Behavior**:
- ✅ Task is decomposed into subtasks (`to_sub_tasks` event)
- ✅ Different agents are assigned (search_agent, document_agent)
- ✅ Subtasks execute in parallel or sequence
- ✅ Results are aggregated
- ✅ Final report is generated

**What to Check**:
- [ ] `to_sub_tasks` event with multiple subtasks
- [ ] Multiple `create_agent` events for different agent types
- [ ] `assign_task` events showing task-agent mapping
- [ ] Workflow diagram shows task tree structure
- [ ] All subtasks complete successfully

---

## 🔐 Test Scenario 4: Provider Validation

**Objective**: Verify model provider validation works correctly.

**Test Steps**:
1. Go to Settings → Providers
2. Add a new provider (e.g., OpenAI with test API key)
3. Click "Validate" button
4. Test with both valid and invalid keys

**Expected Behavior**:
- ✅ Validation endpoint is called with auth
- ✅ Valid API key: Returns `is_valid: true`, `is_tool_calls: true`
- ✅ Invalid API key: Returns `is_valid: false` with error message
- ✅ Tool call support is verified
- ✅ Error messages are user-friendly

**What to Check**:
- [ ] POST `/model/validate` requires authentication
- [ ] Token refresh works if token expires
- [ ] Validation response includes `is_tool_calls` field
- [ ] UI shows validation status correctly
- [ ] Invalid keys show appropriate error messages

---

## 📊 Test Scenario 5: Real-Time Streaming

**Objective**: Verify SSE streaming works correctly for long-running tasks.

**Test Prompt**:
```
Write a comprehensive guide about AI agents. Include:
- Introduction
- Types of agents
- Use cases
- Best practices
- Conclusion

Stream the response as you write it.
```

**Expected Behavior**:
- ✅ Multiple `streaming` events received
- ✅ Text appears incrementally in chat
- ✅ No connection drops or timeouts
- ✅ Final message is complete
- ✅ Typing indicator shows during streaming

**What to Check**:
- [ ] SSE connection stays open
- [ ] `streaming` events arrive continuously
- [ ] UI updates smoothly without lag
- [ ] Connection reconnects if dropped
- [ ] Final `end` event received

---

## 🛠️ Test Scenario 6: Complex Multi-Step Workflow

**Objective**: Test a realistic complex workflow with multiple tools and agents.

**Test Prompt**:
```
I want to analyze a GitHub repository. Here's what I need:
1. Search for "camel-ai/camel" on GitHub
2. Get the repository details (stars, description, main language)
3. Clone the repository (or get README content)
4. Analyze the codebase structure
5. Create a summary document with:
   - Repository overview
   - Key features
   - Tech stack
   - Setup instructions (if available)
6. Save everything to a project folder called "camel-analysis"
```

**Expected Behavior**:
- ✅ Task is properly decomposed
- ✅ Multiple agents work together
- ✅ GitHub toolkit is used correctly
- ✅ File operations create organized folder structure
- ✅ All steps complete successfully
- ✅ Final summary is comprehensive

**What to Check**:
- [ ] `github` toolkit is activated
- [ ] `file` toolkit creates folder structure
- [ ] Multiple agents collaborate
- [ ] Task tree shows all subtasks
- [ ] Artifacts are properly organized
- [ ] No errors or timeouts

---

## ⚠️ Test Scenario 7: Error Handling

**Objective**: Verify system handles errors gracefully.

**Test Prompts**:

**7a. Invalid Tool Usage**:
```
Try to read a file that doesn't exist: /nonexistent/path/file.txt
```

**7b. Network Error**:
```
Search the web for "test" but simulate a network failure
```

**7c. Invalid Provider**:
```
Use a provider with invalid API key and try to execute a task
```

**Expected Behavior**:
- ✅ Errors are caught and logged
- ✅ `error` SSE event is sent
- ✅ User sees friendly error message
- ✅ System doesn't crash
- ✅ Task state shows "FAILED"
- ✅ User can retry or cancel

**What to Check**:
- [ ] `error` events are properly formatted
- [ ] Error messages are user-friendly
- [ ] Failed tasks show in history
- [ ] System recovers gracefully
- [ ] No memory leaks or hanging processes

---

## 🔄 Test Scenario 8: Session Management

**Objective**: Verify session persistence and history tracking.

**Test Steps**:
1. Create a new task and let it complete
2. Check History page
3. Create another task
4. Verify both sessions appear in sidebar
5. Click on old session - verify it loads correctly

**Expected Behavior**:
- ✅ Sessions are saved to database
- ✅ History page shows all sessions
- ✅ Sessions are grouped by project
- ✅ Session titles are auto-generated
- ✅ Clicking session loads chat history
- ✅ SSE events are replayed (if supported)

**What to Check**:
- [ ] POST `/chat/histories` saves session
- [ ] GET `/chat/histories` returns all sessions
- [ ] Sessions appear in sidebar
- [ ] Session details load correctly
- [ ] Token usage is tracked
- [ ] Project grouping works

---

## 🎨 Test Scenario 9: Workflow Visualization

**Objective**: Verify workflow diagram displays correctly.

**Test Prompt**:
```
Create a multi-step data analysis workflow:
1. Fetch data from an API
2. Process the data
3. Generate visualizations
4. Create a report
```

**Expected Behavior**:
- ✅ Workflow diagram appears
- ✅ Task nodes show correct states
- ✅ Agent nodes show assignments
- ✅ Edges connect tasks correctly
- ✅ Status colors update in real-time
- ✅ Diagram is interactive (zoom/pan)

**What to Check**:
- [ ] ReactFlow diagram renders
- [ ] Nodes update on state changes
- [ ] Tool calls appear as nodes/edges
- [ ] Agent assignments visible
- [ ] Task tree structure correct
- [ ] No rendering errors

---

## 🔌 Test Scenario 10: MCP Integration

**Objective**: Verify MCP servers work correctly.

**Test Steps**:
1. Install an MCP server (e.g., Google Drive MCP)
2. Configure it with credentials
3. Use it in a task

**Test Prompt**:
```
Use the Google Drive MCP to list my files and create a summary document.
```

**Expected Behavior**:
- ✅ MCP server connects successfully
- ✅ MCP tools are available to agent
- ✅ Agent can use MCP tools
- ✅ Results are returned correctly
- ✅ Errors are handled gracefully

**What to Check**:
- [ ] MCP server installs correctly
- [ ] MCP tools appear in available tools
- [ ] Agent can call MCP tools
- [ ] MCP responses are formatted correctly
- [ ] Connection errors are handled

---

## 📋 Comprehensive Integration Test

**Objective**: Test the entire system end-to-end with a realistic use case.

**Test Prompt**:
```
I'm building a Python web scraper project. Help me:

1. Research best Python web scraping libraries (requests, BeautifulSoup, Scrapy)
2. Create a project structure with:
   - requirements.txt with the libraries
   - main.py with a basic scraper template
   - README.md with setup instructions
3. Write a simple scraper that fetches the title and first paragraph from a webpage
4. Test the scraper with a sample URL
5. Create a summary document explaining what was built

Use appropriate agents and tools for each step.
```

**Expected Behavior**:
- ✅ All components work together
- ✅ Multiple agents collaborate
- ✅ Files are created correctly
- ✅ Code executes successfully
- ✅ Documentation is generated
- ✅ Final summary is comprehensive

**What to Check**:
- [ ] All SSE events flow correctly
- [ ] No errors or timeouts
- [ ] Files are created in correct structure
- [ ] Code executes and produces output
- [ ] Final summary is accurate
- [ ] Session is saved correctly
- [ ] Workflow diagram shows full flow

---

## 🎯 Success Criteria Checklist

After running all tests, verify:

### Backend
- [ ] All API endpoints respond correctly
- [ ] SSE streaming works without drops
- [ ] Database persists all data
- [ ] Error handling is robust
- [ ] Provider validation works
- [ ] MCP integration functions

### Frontend
- [ ] UI updates in real-time
- [ ] Workflow diagram renders correctly
- [ ] Chat interface is responsive
- [ ] History/sessions load correctly
- [ ] Settings pages work
- [ ] Error messages are user-friendly

### Integration
- [ ] End-to-end workflows complete
- [ ] Multi-agent coordination works
- [ ] Tool calls execute correctly
- [ ] Streaming is smooth
- [ ] Sessions persist correctly
- [ ] No memory leaks or crashes

---

## 🐛 Common Issues to Watch For

1. **SSE Connection Drops**: Check timeout settings, keep-alive
2. **Tool Execution Failures**: Verify tool permissions, paths
3. **Provider Validation Errors**: Check API keys, network connectivity
4. **UI Lag**: Monitor React re-renders, optimize SSE handling
5. **Session Loading**: Verify database queries, caching
6. **Workflow Diagram**: Check ReactFlow node updates, state management

---

## 📝 Notes

- Run tests in order (they build on each other)
- Check browser console for errors
- Monitor backend logs for issues
- Test with different providers (OpenAI, Anthropic, local)
- Test with both valid and invalid inputs
- Verify error recovery mechanisms

---

**Last Updated**: January 2026
**Version**: 1.0

