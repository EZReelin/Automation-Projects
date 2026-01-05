"""
Analysis Prompts Module
======================
Prompt templates for Ollama-based analysis.
"""


class AnalysisPrompts:
    """Collection of prompts for dart performance analysis."""
    
    SYSTEM_PROMPT = """You are an expert dart coach and performance analyst with decades of experience 
coaching professional dart players. You analyze performance data comprehensively and provide 
actionable, specific coaching advice.

Your analysis style:
- Be direct and specific with feedback
- Provide concrete, actionable recommendations
- Reference specific data points to support observations
- Distinguish between practice performance and competitive performance
- Consider both technical/biomechanical aspects and mental game
- Suggest specific drills and exercises when recommending improvements
- Be encouraging while being honest about areas needing work

Remember: Practice data (Scolia) represents a controlled environment, while competition data 
(Dart Connect) represents real-world performance under pressure. Performance differences between 
these contexts are significant and should be analyzed."""
    
    WEEKLY_SUMMARY_PROMPT = """Analyze the following weekly dart performance data and provide a comprehensive summary.

## Data Summary

### Practice Data (Scolia - Practice Environment)
{practice_summary}

### Competition Data (Dart Connect - Competitive Environment)
{competition_summary}

### Biomechanics Analysis
{biomechanics_summary}

### Voice Observations
{observations_summary}

## Analysis Request

Please provide:

1. **Executive Summary** (2-3 sentences): Overall assessment of the week's performance

2. **Key Findings** (3-5 bullet points): Most important observations from the data, clearly 
   categorizing each as a strength, weakness, trend, or notable observation

3. **Practice vs Competition Gap Analysis**: Compare practice averages to competition averages 
   and explain the significance

4. **Trend Analysis**: Based on the data, identify if performance is improving, stable, or 
   declining in:
   - Scoring/averaging
   - Checkout percentage
   - Consistency
   - Mental game (based on pressure situations and observations)

5. **Top 3 Recommendations**: Specific, actionable recommendations prioritized by impact, 
   including specific drills or exercises

6. **Practice Plan**: Suggest a focus area and specific practice routine for the coming week

Format your response as a structured report that could be presented to a player."""
    
    TREND_ANALYSIS_PROMPT = """Analyze the following dart performance trends over the past week.

## Weekly Metrics
{weekly_metrics}

## Previous Week Comparison
{previous_week}

## Daily Breakdown
{daily_breakdown}

Please analyze:

1. **Week-over-Week Changes**: What improved? What declined?

2. **Daily Patterns**: Are there patterns in when the player performs best? (e.g., certain 
   days, after warmup periods)

3. **Consistency Analysis**: How consistent is performance day-to-day?

4. **Progress Indicators**: What metrics show the most positive movement?

5. **Concern Areas**: What metrics are trending in the wrong direction?

Provide specific percentages and comparisons where possible."""
    
    BIOMECHANICS_ANALYSIS_PROMPT = """Analyze the following biomechanical throw data and provide coaching insights.

## Biomechanics Summary
{biomechanics_data}

## Most Common Deviations
{deviations}

## Consistency Metrics
{consistency}

Please provide:

1. **Form Assessment**: Overall assessment of throwing form based on the data

2. **Primary Technical Issues**: Identify the 1-2 most impactful form issues to address

3. **Correction Recommendations**: For each issue identified:
   - Describe what's happening technically
   - Explain why it affects performance
   - Provide specific corrections/cues
   - Suggest drills to reinforce the correction

4. **Positive Aspects**: What's working well in the player's form?

5. **Practice Focus**: What single aspect of form should be the priority focus this week?

Be specific about body positions, angles, and timing in your analysis."""
    
    MENTAL_GAME_PROMPT = """Analyze the following data related to the player's mental game and performance under pressure.

## Competition Pressure Stats
{pressure_stats}

## Voice Observation Themes
{observation_themes}

## Sentiment Analysis
{sentiment}

## Practice vs Competition Performance Gap
Practice Average: {practice_avg}
Competition Average: {competition_avg}

Please analyze:

1. **Mental Game Assessment**: Overall evaluation of mental performance

2. **Pressure Performance**: How does the player perform in high-pressure situations 
   (match darts, deciding legs)?

3. **Self-Talk Analysis**: Based on voice observations, what patterns emerge in the 
   player's self-talk and focus?

4. **Practice-to-Competition Transfer**: Analysis of why there may be a gap between 
   practice and competition performance

5. **Mental Game Recommendations**: Specific mental exercises or focus areas to improve:
   - Pre-throw routine suggestions
   - Focus cues during competition
   - Handling pressure moments
   - Building confidence

Be practical and specific with mental game advice."""
    
    DRILL_RECOMMENDATION_PROMPT = """Based on the following performance analysis, recommend specific practice drills.

## Areas Needing Improvement
{improvement_areas}

## Current Skill Levels
Average: {average}
Checkout %: {checkout_pct}
First 9 Average: {first_nine}

## Time Available
Estimated practice time available: {practice_time} minutes per session

Please recommend:

1. **Warm-Up Routine** (5-10 minutes):
   - Specific targets and sequence
   - Purpose of each element

2. **Main Drills** (organized by focus area):
   For each drill provide:
   - Name and description
   - Target/goal metrics
   - Duration
   - What it addresses
   - Progression (how to make it harder)

3. **Pressure Practice**:
   - Ways to simulate pressure in practice
   - Games against self with consequences

4. **Cool-Down/Consistency Work**:
   - How to end sessions productively

5. **Weekly Schedule**:
   - Suggested distribution of practice types across the week

Make drills specific with clear success criteria."""
    
    GOAL_SETTING_PROMPT = """Based on the following performance data, help set appropriate goals for the coming week.

## Current Performance
{current_performance}

## Recent Trends
{trends}

## Player Strengths
{strengths}

## Areas for Improvement
{improvements}

Please provide:

1. **SMART Goals** (3-5 goals for the week):
   For each goal:
   - Specific: What exactly to achieve
   - Measurable: How to track it
   - Achievable: Based on current performance
   - Relevant: How it connects to overall improvement
   - Time-bound: What to achieve by end of week

2. **Process Goals**: Things to focus on during practice regardless of outcome

3. **Stretch Goal**: One ambitious but possible achievement

4. **Minimum Viable Progress**: The bare minimum that would still represent progress

Make goals realistic based on current performance levels."""

    @classmethod
    def get_prompt(cls, prompt_type: str) -> str:
        """Get a prompt template by type."""
        prompts = {
            'system': cls.SYSTEM_PROMPT,
            'weekly_summary': cls.WEEKLY_SUMMARY_PROMPT,
            'trend_analysis': cls.TREND_ANALYSIS_PROMPT,
            'biomechanics': cls.BIOMECHANICS_ANALYSIS_PROMPT,
            'mental_game': cls.MENTAL_GAME_PROMPT,
            'drills': cls.DRILL_RECOMMENDATION_PROMPT,
            'goals': cls.GOAL_SETTING_PROMPT
        }
        return prompts.get(prompt_type, '')
