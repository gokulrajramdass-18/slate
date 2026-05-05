"""
Seed script for system prompt templates

This script generates INSERT statements for all 28 system prompt templates.
Can be run standalone or imported by migration scripts.
"""

def generate_orchestration_inserts():
    """Generate INSERT statements for orchestration prompts (5)"""
    prompts = [
        {
            "id": "sys-prompt-orch-analysis",
            "key": "orchestration_query_analysis",
            "name": "Orchestration: Query Analysis",
            "desc": "Analyzes query complexity and determines execution requirements",
            "prompt": '''You are an expert task planner. Return responses in pure JSON format only, no markdown or code blocks.

Analyze this query and determine:
1. **Complexity**: Simple (single step), Medium (2-3 steps), Complex (4+ steps)
2. **Required Tools**: Which tools are needed and why
3. **Required Sources**: Which data sources should be consulted
4. **Approach**: How to break down the task
5. **Estimated Steps**: How many execution steps will be needed

Query: {query}
Role: {role}
Available Tools: {tools_description}
Available Sources: {sources_description}
Context: {source_context}

Return ONLY valid JSON: {{"complexity": "simple|medium|complex", "required_tools": ["tool1"], "required_sources": ["source1"], "approach": "description", "estimated_steps": 1, "reasoning": "why"}}''',
            "vars": '[{"name": "query", "type": "string", "required": true}, {"name": "role", "type": "string", "required": true}, {"name": "tools_description", "type": "string", "required": true}, {"name": "sources_description", "type": "string", "required": true}, {"name": "source_context", "type": "string", "required": false}]',
            "meta": '{"output_format": "json", "composition": "base"}'
        },
        {
            "id": "sys-prompt-orch-planning",
            "key": "orchestration_execution_planning",
            "name": "Orchestration: Execution Planning",
            "desc": "Creates detailed step-by-step execution plan with tool selection",
            "prompt": '''You are an expert execution planner. Return responses in pure JSON format only, no markdown or code blocks.

Create a detailed execution plan for this query.

Query: {query}
Role: {role}
Analysis: {analysis}
Available Tools: {tools_with_params}
Source Context: {source_context}

Create a step-by-step plan. Each step should:
1. Have a clear objective
2. Use the most appropriate tool
3. Include specific tool arguments
4. Build on results from previous steps (if applicable)

Return ONLY valid JSON array: [{{"step_number": 1, "step_name": "Search", "tool_name": "web_search", "tool_args": {{"query": "..."}}, "expected_output": "...", "depends_on": []}}]

Keep it efficient: {estimated_steps} steps maximum.''',
            "vars": '[{"name": "query", "type": "string", "required": true}, {"name": "role", "type": "string", "required": true}, {"name": "analysis", "type": "string", "required": true}, {"name": "tools_with_params", "type": "string", "required": true}, {"name": "source_context", "type": "string", "required": false}, {"name": "estimated_steps", "type": "integer", "required": true}]',
            "meta": '{"output_format": "json", "composition": "base"}'
        },
        {
            "id": "sys-prompt-orch-llm",
            "key": "orchestration_llm_step",
            "name": "Orchestration: LLM Step Execution",
            "desc": "Executes individual step via LLM (when no specific tool available)",
            "prompt": '''You are a {role} agent.

Execute this step: {step_name}

Original Query: {query}
Role: {role}

Previous Results:
{previous_results}

Source Context:
{source_context}

Provide a detailed response for this step.''',
            "vars": '[{"name": "role", "type": "string", "required": true}, {"name": "step_name", "type": "string", "required": true}, {"name": "query", "type": "string", "required": true}, {"name": "previous_results", "type": "string", "required": false}, {"name": "source_context", "type": "string", "required": false}]',
            "meta": '{"output_format": "text", "composition": "base"}'
        },
        {
            "id": "sys-prompt-orch-synthesis",
            "key": "orchestration_results_synthesis",
            "name": "Orchestration: Results Synthesis",
            "desc": "Synthesizes single-agent execution results into final answer",
            "prompt": '''You are a {role} agent synthesizing research findings.

Synthesize the final answer for this query.

Original Query: {query}
Role: {role}

Execution Summary:
- Total steps executed: {total_steps}
- Successful steps: {successful_steps}
- Failed steps: {failed_steps}
{errors_summary}

Step Results:
{results_summary}

Synthesize a comprehensive, well-structured final answer that:
1. Directly addresses the original query
2. Incorporates findings from all successful steps
3. Presents information clearly and professionally
4. Acknowledges any limitations due to errors
5. Provides actionable insights based on the {role} role

Format as markdown for readability.''',
            "vars": '[{"name": "role", "type": "string", "required": true}, {"name": "query", "type": "string", "required": true}, {"name": "total_steps", "type": "integer", "required": true}, {"name": "successful_steps", "type": "integer", "required": true}, {"name": "failed_steps", "type": "integer", "required": true}, {"name": "errors_summary", "type": "string", "required": false}, {"name": "results_summary", "type": "string", "required": true}]',
            "meta": '{"output_format": "markdown", "composition": "base"}'
        },
        {
            "id": "sys-prompt-orch-multi",
            "key": "orchestration_multi_agent",
            "name": "Orchestration: Multi-Agent Consolidation",
            "desc": "Consolidates results from multiple agents into unified answer",
            "prompt": '''You are a {role} agent consolidating multi-agent findings.

Consolidate the following results from multiple agents into a comprehensive final answer.

Original Query: {query}
Role: {role}

Agent Results:
{results_text}

Source Context:
{source_context}

Synthesize a comprehensive, well-structured final answer that:
1. Directly addresses the original query
2. Integrates findings from all agents
3. Presents information clearly and professionally
4. Provides actionable insights based on the {role} role

Format as markdown for readability.''',
            "vars": '[{"name": "role", "type": "string", "required": true}, {"name": "query", "type": "string", "required": true}, {"name": "results_text", "type": "string", "required": true}, {"name": "source_context", "type": "string", "required": false}]',
            "meta": '{"output_format": "markdown", "composition": "base"}'
        }
    ]

    inserts = []
    for p in prompts:
        # Escape single quotes for SQL
        prompt_escaped = p["prompt"].replace("'", "''")

        insert = f'''INSERT OR IGNORE INTO system_prompt_templates (id, category, template_key, name, description, prompt_text, default_prompt_text, variables, metadata, is_default, is_active, created, updated)
VALUES (
    '{p["id"]}',
    'orchestration',
    '{p["key"]}',
    '{p["name"]}',
    '{p["desc"]}',
    '{prompt_escaped}',
    '{prompt_escaped}',
    '{p["vars"]}',
    '{p["meta"]}',
    1, 1,
    datetime('now'), datetime('now')
);
'''
        inserts.append(insert)

    return "\n".join(inserts)


def generate_microsite_inserts():
    """Generate INSERT statements for microsite prompts (15)"""
    # Simplified for now - in production these would have full section prompts
    sections = [
        ("hero", "Expert copywriter creating compelling hero section"),
        ("summary", "Business analyst creating executive summary"),
        ("insights", "Data analyst presenting key findings"),
        ("features", "Product marketer creating features section"),
        ("call_to_action", "Conversion specialist"),
        ("conclusion", "Strategic writer crafting forward-looking conclusion"),
        ("about", "Brand storyteller creating About section"),
        ("pricing", "Pricing strategist"),
        ("testimonials", "Social proof curator"),
        ("faq", "UX writer creating helpful FAQ"),
        ("footer", "Minimalist designer"),
        ("toc", "Technical writer creating table of contents"),
        ("sources_list", "Research librarian curating sources"),
        ("default", "Professional web content writer"),
        ("editor_chat", "Microsite editing assistant")
    ]

    inserts = []
    for key, desc in sections:
        prompt = f'''Generate professional, modern content for the "{key}" section of a microsite.

Title: {{title}}
Template: {{template_name}}
User Instructions: {{user_prompt}}
Source Context: {{source_context}}

Create engaging, well-formatted markdown content that follows best practices for {key} sections.'''

        prompt_escaped = prompt.replace("'", "''")

        insert = f'''INSERT OR IGNORE INTO system_prompt_templates (id, category, template_key, name, description, prompt_text, default_prompt_text, variables, metadata, is_default, is_active, created, updated)
VALUES (
    'sys-prompt-micro-{key}',
    'microsite',
    'microsite_{key}',
    'Microsite: {key.replace("_", " ").title()}',
    '{desc}',
    '{prompt_escaped}',
    '{prompt_escaped}',
    '{{"variables": [{{"name": "title", "type": "string", "required": true}}, {{"name": "template_name", "type": "string", "required": true}}, {{"name": "user_prompt", "type": "string", "required": false}}, {{"name": "source_context", "type": "string", "required": false}}]}}',
    '{{"output_format": "markdown", "composition": "base"}}',
    1, 1,
    datetime('now'), datetime('now')
);
'''
        inserts.append(insert)

    return "\n".join(inserts)


if __name__ == "__main__":
    print("-- Orchestration Prompts (5)")
    print(generate_orchestration_inserts())
    print("\n-- Microsite Prompts (15)")
    print(generate_microsite_inserts())
