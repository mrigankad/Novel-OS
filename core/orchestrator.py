"""
Novel OS - Workflow Orchestrator

Central orchestration system that coordinates agents through the novel writing workflow.
"""

import json
import argparse
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Import state manager
from state_manager import StoryState, Character, PlotThread, ChapterState, TimelineEvent, StyleProfile, initialize_project

# Import NIM client (optional - for AI-powered generation)
try:
    from nim_client import NIMClient, AgentRunner, NIM_MODELS
    NIM_AVAILABLE = True
except ImportError:
    NIM_AVAILABLE = False

# Import token management (optional - enhances NIM integration)
try:
    from token_manager import (
        estimate_tokens, get_model_limits, trim_to_token_budget,
        SmartPromptBuilder, ChunkedWriter, ChapterSummarizer,
        trim_characters_context, trim_plot_threads_context,
        print_token_report,
    )
    TOKEN_MGMT_AVAILABLE = True
except ImportError:
    TOKEN_MGMT_AVAILABLE = False


class NovelOrchestrator:
    """
    Orchestrates the novel writing workflow across all agents.
    """
    
    def __init__(self, project_path: str = ".", nim_api_key: str = "", nim_model: str = "", chunk_limit: Optional[int] = None):
        self.project_path = Path(project_path)
        self.state = StoryState(project_path)
        self.agents_dir = Path(__file__).parent.parent / "agents"
        self.templates_dir = Path(__file__).parent.parent / "templates"
        self.outputs_dir = self.project_path / "outputs"
        self.manuscript_dir = self.outputs_dir / "manuscript"
        self.feedback_dir = self.outputs_dir / "feedback"
        
        # NIM integration
        self.nim_client = None
        self.agent_runner = None
        self.chapter_summarizer = None
        self.chunked_writer = None
        self.prompt_builder = None
        
        # Initialize chapter summarizer (works even without NIM)
        if TOKEN_MGMT_AVAILABLE:
            self.chapter_summarizer = ChapterSummarizer(str(self.project_path))
        
        if nim_api_key and NIM_AVAILABLE:
            try:
                model = nim_model or "llama-3.1-70b"
                self.nim_client = NIMClient(
                    api_key=nim_api_key,
                    default_model=model,
                )
                self.agent_runner = AgentRunner(self.nim_client, str(self.agents_dir))
                print(f"🟢 NIM API connected (model: {model})")
                
                # Initialize token-aware components
                if TOKEN_MGMT_AVAILABLE:
                    self.chunked_writer = ChunkedWriter(self.agent_runner, custom_word_target=chunk_limit)
                    self.prompt_builder = SmartPromptBuilder(model)
                    limits = get_model_limits(model)
                    print(f"   Context window: {limits.context_window:,} tokens")
                    print(f"   Max output: {limits.max_output_tokens:,} tokens")
            except Exception as e:
                print(f"⚠️  NIM setup failed: {e}. Running in offline/prompt-only mode.")
        
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create output directories."""
        self.manuscript_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
    
    # ===== Project Initialization =====
    
    def init_project(self, title: str, genre: str, author: str = "") -> str:
        """Initialize a new novel project."""
        print(f"🎭 Initializing new project: '{title}'")
        print(f"   Genre: {genre}")
        
        # Initialize state
        state = initialize_project(str(self.project_path), title, genre)
        
        if author:
            state.set_metadata('author', author)
        
        # Create project structure
        self._create_project_files(title, genre)
        
        state.save_state()
        
        print(f"✅ Project initialized!")
        print(f"   State file: outputs/state/story_state.json")
        print(f"   Next step: Define your characters and story bible")
        
        return str(self.project_path)
    
    def _create_project_files(self, title: str, genre: str):
        """Create initial project template files."""
        # Create story bible template
        bible_path = self.outputs_dir / "story_bible.md"
        bible_content = f"""# Story Bible: {title}

## 📚 Genre
{genre}

## 🎭 Themes
- [Theme 1]
- [Theme 2]
- [Theme 3]

## 🎨 Tone
[Describe the emotional tone of the story]

## 🌍 Setting

### Time Period
[When does the story take place?]

### Primary Locations
- [Location 1]: [Description]
- [Location 2]: [Description]

### World Rules
[Magic system, technology level, social structures, etc.]

## 📖 Structure
- Target Word Count: 80,000
- Estimated Chapters: 32
- POV: Third Person Limited
- Tense: Past

## 👥 Character Roster
[Link to character profiles]

## 🔗 Plot Overview
[Brief summary of main story]

## 📝 Notes
[Any additional world-building notes]
"""
        bible_path.write_text(bible_content, encoding='utf-8')
        
        # Create character template
        char_template_path = self.templates_dir / "character_profile.md"
        char_template_path.parent.mkdir(parents=True, exist_ok=True)
        char_template = """# Character Profile: [Name]

## Basic Information
- **Full Name**: 
- **Age**: 
- **Role**: [Protagonist/Antagonist/Supporting]
- **Occupation**: 

## Physical Appearance
- Height: 
- Build: 
- Hair: 
- Eyes: 
- Distinguishing Features: 

## Psychology
- **Internal Desire**: [What do they want emotionally?]
- **External Goal**: [What are they trying to achieve?]
- **Fear**: [What terrifies them?]
- **Weakness**: [Character flaw]
- **Strength**: [Key virtue/skill]
- **Secret**: [What are they hiding?]

## Character Arc
- **Starting State**: 
- **Transformation**: 
- **Ending State**: 

## Relationships
- [Character Name]: [Relationship type and dynamics]

## Voice
- **Speech Patterns**: 
- **Vocabulary Level**: 
- **Common Phrases**: 

## Background
[Backstory that shaped them]

## Notes
[Additional details]
"""
        char_template_path.write_text(char_template, encoding='utf-8')
    
    # ===== Character Management =====
    
    def add_character(self, name: str, role: str, **kwargs) -> str:
        """Add a new character to the project."""
        char_id = f"char_{len(self.state.characters) + 1:03d}"
        
        character = Character(
            id=char_id,
            full_name=name,
            role=role,
            **kwargs
        )
        
        self.state.add_character(character)
        self.state.save_state()
        
        print(f"✅ Added character: {name} ({char_id})")
        return char_id
    
    def list_characters(self):
        """List all characters in the project."""
        chars = self.state.get_all_characters()
        
        if not chars:
            print("No characters defined yet.")
            return
        
        print("\n👥 Characters:")
        print("-" * 60)
        for char in chars:
            arc_info = f"{char.arc_stage} ({char.arc_progress}%)"
            print(f"  {char.id}: {char.full_name} ({char.role})")
            print(f"      Arc: {arc_info}")
            if char.current_location:
                print(f"      Location: {char.current_location}")
            print()
    
    # ===== Plot Management =====
    
    def add_plot_thread(self, name: str, description: str, thread_type: str = "main", priority: int = 3) -> str:
        """Add a new plot thread."""
        thread_id = f"plot_{len(self.state.plot_threads) + 1:03d}"
        
        thread = PlotThread(
            id=thread_id,
            name=name,
            description=description,
            thread_type=thread_type,
            priority=priority
        )
        
        self.state.add_plot_thread(thread)
        self.state.save_state()
        
        print(f"✅ Added plot thread: {name} ({thread_id})")
        return thread_id
    
    def list_plot_threads(self):
        """List all plot threads."""
        threads = list(self.state.plot_threads.values())
        
        if not threads:
            print("No plot threads defined yet.")
            return
        
        print("\n🔗 Plot Threads:")
        print("-" * 60)
        for thread in sorted(threads, key=lambda t: -t.priority):
            status_icon = "🟢" if thread.status == "active" else "🔴" if thread.status == "resolved" else "🟡"
            print(f"  {status_icon} [{thread.priority}] {thread.name} ({thread.thread_type})")
            print(f"      Status: {thread.status}")
            print(f"      {thread.description[:80]}...")
            print()
    
    # ===== Planning Phase =====
    
    def plan_outline(self, num_chapters: int = 32, target_words: int = 80000):
        """Generate a high-level story outline using the Architect agent."""
        print("\n🏗️  ARCHITECT: Creating story outline...")
        print(f"   Target: {num_chapters} chapters, ~{target_words:,} words")
        
        # If NIM is available, use AI to generate the outline
        if self.agent_runner:
            task_prompt = self._build_outline_task_prompt(num_chapters, target_words)
            ai_outline = self.agent_runner.run_agent(
                agent_name="architect",
                task_prompt=task_prompt,
                temperature=0.7,
                max_tokens=4096,
                stream=True,
            )
            # Save AI-generated outline as markdown
            outline_md_path = self.outputs_dir / "outline_ai.md"
            outline_md_path.write_text(ai_outline, encoding='utf-8')
            print(f"\n✅ AI-generated outline saved: {outline_md_path}")
        
        # Also create the structured JSON outline (template)
        outline = {
            'metadata': {
                'title': self.state.metadata.get('title', 'Untitled'),
                'genre': self.state.metadata.get('genre', 'Unknown'),
                'target_chapters': num_chapters,
                'target_word_count': target_words,
                'created': datetime.now().isoformat()
            },
            'acts': self._generate_act_structure(num_chapters),
            'chapter_summaries': self._generate_chapter_templates(num_chapters)
        }
        
        # Save outline
        outline_path = self.outputs_dir / "outline.json"
        with open(outline_path, 'w', encoding='utf-8') as f:
            json.dump(outline, f, indent=2)
        
        print(f"✅ Outline template created: {outline_path}")
        print(f"\n📝 Next: Review outline and run 'plan chapter --number 1'")
        
        return outline
    
    def _build_outline_task_prompt(self, num_chapters: int, target_words: int) -> str:
        """Build a task prompt for the Architect to generate an outline."""
        title = self.state.metadata.get('title', 'Untitled')
        genre = self.state.metadata.get('genre', 'Unknown')
        
        characters = self.state.get_all_characters()
        char_section = ""
        if characters:
            char_section = "\n## Existing Characters\n"
            for c in characters:
                char_section += f"- **{c.full_name}** ({c.role}): {c.internal_desire or 'No desire defined'}\n"
        
        threads = list(self.state.plot_threads.values())
        plot_section = ""
        if threads:
            plot_section = "\n## Existing Plot Threads\n"
            for t in threads:
                plot_section += f"- **{t.name}** ({t.thread_type}): {t.description}\n"
        
        return f"""Create a detailed story outline for the following novel:

# Project Details
- **Title**: {title}
- **Genre**: {genre}
- **Target Chapters**: {num_chapters}
- **Target Word Count**: {target_words:,}
{char_section}
{plot_section}

Provide a complete outline with:
1. A compelling logline
2. Theme statement
3. Three-act structure with chapter assignments
4. Beat sheet with all major story beats
5. Character arc maps for each main character
6. Chapter-by-chapter summary (one paragraph each)
"""
    
    def _generate_act_structure(self, num_chapters: int) -> List[Dict]:
        """Generate a 3-act structure template."""
        act1_end = int(num_chapters * 0.25)
        act2_end = int(num_chapters * 0.75)
        
        return [
            {
                'act_number': 1,
                'name': 'Setup',
                'chapters': list(range(1, act1_end + 1)),
                'percent': 25,
                'key_beats': [
                    'Opening Image',
                    'Theme Stated',
                    'Setup',
                    'Catalyst',
                    'Debate'
                ]
            },
            {
                'act_number': 2,
                'name': 'Confrontation',
                'chapters': list(range(act1_end + 1, act2_end + 1)),
                'percent': 50,
                'key_beats': [
                    'Break into Two',
                    'B Story',
                    'Fun and Games',
                    'Midpoint',
                    'Bad Guys Close In',
                    'All Is Lost',
                    'Dark Night'
                ]
            },
            {
                'act_number': 3,
                'name': 'Resolution',
                'chapters': list(range(act2_end + 1, num_chapters + 1)),
                'percent': 25,
                'key_beats': [
                    'Break into Three',
                    'Finale',
                    'Final Image'
                ]
            }
        ]
    
    def _generate_chapter_templates(self, num_chapters: int) -> List[Dict]:
        """Generate empty chapter templates."""
        return [
            {
                'number': i,
                'title': f'Chapter {i}',
                'status': 'planned',
                'pov_character': '',
                'summary': '',
                'word_count_target': 2500,
                'scenes': []
            }
            for i in range(1, num_chapters + 1)
        ]
    
    def plan_chapter(self, chapter_number: int, summary: str = "", pov: str = ""):
        """Plan a specific chapter in detail."""
        print(f"\n📋 Planning Chapter {chapter_number}...")
        
        # Create or update chapter state
        chapter = self.state.get_chapter(chapter_number)
        if not chapter:
            chapter = self.state.create_chapter(chapter_number)
        
        if summary:
            chapter.plot_advances.append(summary)
        
        if pov:
            chapter.pov_character = pov
        
        chapter.status = 'planned'
        self.state.save_state()
        
        # Generate chapter prompt for Scribe
        prompt = self._generate_chapter_prompt(chapter)
        
        prompt_path = self.outputs_dir / f"chapter_{chapter_number:03d}_prompt.md"
        prompt_path.write_text(prompt, encoding='utf-8')
        
        print(f"✅ Chapter {chapter_number} planned")
        print(f"   Prompt saved: {prompt_path}")
    
    def _generate_chapter_prompt(self, chapter: ChapterState) -> str:
        """Generate a detailed prompt for the Scribe agent."""
        
        # Get context from state
        characters = self.state.get_all_characters()
        active_threads = self.state.get_active_plot_threads()
        
        chapter_info = f"""# SCRIBE PROMPT: Chapter {chapter.number}

## Chapter Information
- **Number**: {chapter.number}
- **Title**: {chapter.title or 'TBD'}
- **POV Character**: {chapter.pov_character or '[Specify]'}
- **Target Word Count**: {chapter.target_word_count}"""

        writing_instructions = f"""## Chapter Goals
- [Primary plot advancement]
- [Character development moment]
- [Emotional beat to hit]

## Scene Outline
1. [Scene 1: Opening hook]
2. [Scene 2: Complication]
3. [Scene 3: Climax/Resolution]

## Writing Requirements
- Maintain deep POV for {chapter.pov_character or '[POV character]'}
- Include at least 3 sensory details
- End with a compelling hook
- Target: {chapter.target_word_count} words

---

**Write the complete chapter now. Follow all protocols in your system instructions.**"""

        style_context = f"""- Tone: {self.state.style_profile.tone}
- POV: {self.state.style_profile.point_of_view}
- Style: {self.state.style_profile.prose_style}"""

        # Use SmartPromptBuilder if available for token-aware context
        if TOKEN_MGMT_AVAILABLE and self.prompt_builder and self.agent_runner:
            budget = self.prompt_builder.limits.recommended_input
            char_context = trim_characters_context(characters, budget // 4, chapter.number)
            thread_context = trim_plot_threads_context(active_threads, budget // 4)
            history_context = self.chapter_summarizer.get_context_for_chapter(chapter.number, budget // 4) if self.chapter_summarizer else ""
            
            system_prompt = self.agent_runner._load_agent_prompt("scribe")
            final_prompt, stats = self.prompt_builder.build_writing_prompt(
                system_prompt=system_prompt,
                chapter_info=chapter_info,
                characters_context=char_context,
                plot_threads_context=thread_context,
                style_context=style_context,
                history_context=history_context,
                writing_instructions=writing_instructions,
            )
            print_token_report("Scribe Prompt Generation", stats)
            return final_prompt

        # Fallback to naive prompt construction (offline mode)
        prompt = f"{chapter_info}\n\n## Story Context\n\n### Characters in This Chapter\n"
        
        for char in characters:
            if char.last_appearance_chapter >= chapter.number - 3:
                prompt += f"\n**{char.full_name}** ({char.role})\n"
                prompt += f"- Current Location: {char.current_location or 'Unknown'}\n"
                prompt += f"- Emotional State: {char.emotional_state or 'Unknown'}\n"
                prompt += f"- Arc Stage: {char.arc_stage} ({char.arc_progress}%)\n"
        
        prompt += "\n### Active Plot Threads\n"
        for thread in active_threads[:5]:  # Top 5 active threads
            prompt += f"- **{thread.name}**: {thread.description[:100]}...\n"
        
        prompt += f"""
### Previous Chapter Recap
[Summary of Chapter {chapter.number - 1}]

{writing_instructions}

## Style Profile
{style_context}
"""
        return prompt
    
    # ===== Writing Phase =====
    
    def write_chapter(self, chapter_number: int, draft_text: str = ""):
        """Process a chapter draft through the workflow."""
        print(f"\n✍️  Writing Chapter {chapter_number}...")
        
        chapter = self.state.get_chapter(chapter_number)
        if not chapter:
            print(f"❌ Chapter {chapter_number} not found. Run 'plan chapter --number {chapter_number}' first.")
            return
        
        # If draft text provided, save it
        if draft_text:
            chapter.status = 'drafted'
            chapter.word_count = len(draft_text.split())
            
            # Save draft
            draft_path = self.manuscript_dir / f"chapter_{chapter_number:03d}_draft.md"
            draft_path.write_text(draft_text, encoding='utf-8')
            
            print(f"   Draft saved: {draft_path}")
        elif self.agent_runner:
            # Use NIM AI to generate the chapter
            prompt = self._generate_chapter_prompt(chapter)
            
            # Check if chunked generation is needed
            if self.chunked_writer and self.chunked_writer.needs_chunking(chapter.target_word_count):
                print(f"   🤖 Generating chapter with AI (chunked mode)...")
                print(f"   Chapter target ({chapter.target_word_count} words) exceeds single-call limit")
                ai_draft = self.chunked_writer.generate_chapter_chunked(
                    base_prompt=prompt,
                    target_word_count=chapter.target_word_count,
                    agent_name="scribe",
                    temperature=0.8,
                    stream=True,
                )
            else:
                print(f"   🤖 Generating chapter with AI (Scribe agent)...")
                ai_draft = self.agent_runner.run_agent(
                    agent_name="scribe",
                    task_prompt=prompt,
                    temperature=0.8,
                    max_tokens=4096,
                    stream=True,
                )
            
            chapter.status = 'drafted'
            chapter.word_count = len(ai_draft.split())
            
            draft_path = self.manuscript_dir / f"chapter_{chapter_number:03d}_draft.md"
            draft_path.write_text(ai_draft, encoding='utf-8')
            
            print(f"\n   ✅ AI draft saved: {draft_path}")
            print(f"   Word count: {chapter.word_count}")
        else:
            print(f"   No draft text provided and NIM not configured.")
            print(f"   Use prompt: outputs/chapter_{chapter_number:03d}_prompt.md")
            print(f"   Or add --nim-key to enable AI generation.")
        
        self.state.save_state()
    
    def submit_draft(self, chapter_number: int, draft_path: str):
        """Submit a draft file for a chapter."""
        draft_file = Path(draft_path)
        if not draft_file.exists():
            print(f"❌ Draft file not found: {draft_path}")
            return
        
        draft_text = draft_file.read_text(encoding='utf-8')
        self.write_chapter(chapter_number, draft_text)
        
        print(f"✅ Draft submitted for Chapter {chapter_number}")
        print(f"   Next: Run 'edit chapter --number {chapter_number}'")
    
    # ===== Editing Phase =====
    
    def edit_chapter(self, chapter_number: int, mode: str = "line"):
        """Process a chapter through editing workflow."""
        print(f"\n🔍 EDITING Chapter {chapter_number} (Mode: {mode})")
        
        chapter = self.state.get_chapter(chapter_number)
        if not chapter:
            print(f"❌ Chapter {chapter_number} not found.")
            return
        
        if chapter.status not in ['drafted', 'editing']:
            print(f"❌ Chapter {chapter_number} has no draft to edit.")
            return
        
        # Load draft
        draft_path = self.manuscript_dir / f"chapter_{chapter_number:03d}_draft.md"
        if not draft_path.exists():
            print(f"❌ Draft file not found: {draft_path}")
            return
        
        draft_text = draft_path.read_text(encoding='utf-8')
        
        # Generate editing prompt
        edit_prompt = self._generate_edit_prompt(chapter, draft_text, mode)
        
        if self.agent_runner:
            # Use NIM AI for editing
            print(f"   🤖 Running Editor agent with AI...")
            ai_edit = self.agent_runner.run_agent(
                agent_name="editor",
                task_prompt=edit_prompt,
                temperature=0.5,  # Lower temperature for editing precision
                max_tokens=4096,
                stream=True,
            )
            
            # Save AI editor feedback and revised text
            feedback_path = self.feedback_dir / f"chapter_{chapter_number:03d}_editor_feedback.md"
            feedback_path.write_text(ai_edit, encoding='utf-8')
            
            print(f"\n   ✅ Editor feedback saved: {feedback_path}")
            chapter.status = 'editing'
        else:
            # Offline mode: save the prompt for manual use
            edit_prompt_path = self.feedback_dir / f"chapter_{chapter_number:03d}_edit_prompt.md"
            edit_prompt_path.write_text(edit_prompt, encoding='utf-8')
            chapter.status = 'editing'
            print(f"✅ Editing prompt created: {edit_prompt_path}")
        
        self.state.save_state()
    
    def _generate_edit_prompt(self, chapter: ChapterState, draft_text: str, mode: str) -> str:
        """Generate an editing prompt."""
        return f"""# EDITOR PROMPT: Chapter {chapter.number}

## Editing Mode: {mode.upper()}

## Chapter Information
- **Number**: {chapter.number}
- **POV**: {chapter.pov_character}
- **Current Word Count**: {chapter.word_count}
- **Target**: {chapter.target_word_count}

## Original Draft

```markdown
{draft_text}
```

## Editing Instructions

### Mode-Specific Focus: {mode}
""" + {
            "line": """
- Fix awkward phrasing
- Strengthen verbs
- Remove filter words (saw, felt, thought, etc.)
- Improve sentence rhythm
- Eliminate wordiness
""",
            "developmental": """
- Verify scene goals are clear
- Check escalation
- Improve transitions between scenes
- Enhance emotional arc
- Strengthen chapter hook
""",
            "pacing": """
- Identify and fix slow sections
- Compress exposition
- Accelerate action sequences
- Vary scene lengths
- Check chapter-ending momentum
""",
            "dialogue": """
- Ensure natural speech patterns
- Add subtext
- Optimize dialogue tags
- Verify distinct character voices
- Remove on-the-nose dialogue
""",
            "tension": """
- Raise stakes where flat
- Add micro-tension
- Strengthen chapter ending
- Create anticipation
- Deepen conflict
"""
        }.get(mode, "- General line editing") + f"""

## Style Profile to Maintain
- Tone: {self.state.style_profile.tone}
- Prose Style: {self.state.style_profile.prose_style}
- POV: {self.state.style_profile.point_of_view}

## Output Format
Provide:
1. EDITOR_ANALYSIS section with issues found
2. REVISED_CHAPTER with the full edited text
3. EDITOR_STATE_UPDATE with changes summary

---

**Edit the chapter now. Follow your system instructions.**
"""
    
    def submit_edit(self, chapter_number: int, edited_path: str):
        """Submit an edited chapter."""
        edit_file = Path(edited_path)
        if not edit_file.exists():
            print(f"❌ Edit file not found: {edited_path}")
            return
        
        # Copy to manuscript as revised
        revised_path = self.manuscript_dir / f"chapter_{chapter_number:03d}_revised.md"
        import shutil
        shutil.copy(edit_file, revised_path)
        
        chapter = self.state.get_chapter(chapter_number)
        if chapter:
            chapter.status = 'edited'
            self.state.save_state()
        
        print(f"✅ Edit submitted for Chapter {chapter_number}")
        print(f"   Next: Run 'validate chapter --number {chapter_number}'")
    
    # ===== Validation Phase =====
    
    def validate_chapter(self, chapter_number: int):
        """Run continuity and style validation on a chapter."""
        print(f"\n🛡️  VALIDATING Chapter {chapter_number}...")
        
        chapter = self.state.get_chapter(chapter_number)
        if not chapter:
            print(f"❌ Chapter {chapter_number} not found.")
            return
        
        # Load the chapter text
        for suffix in ['_revised', '_draft']:
            text_path = self.manuscript_dir / f"chapter_{chapter_number:03d}{suffix}.md"
            if text_path.exists():
                chapter_text = text_path.read_text(encoding='utf-8')
                break
        else:
            print(f"❌ No chapter file found.")
            return
        
        # Generate validation prompt for Continuity Guardian
        validation_prompt = self._generate_validation_prompt(chapter_number, chapter_text)
        
        if self.agent_runner:
            # Use NIM AI for validation
            print(f"   🤖 Running Continuity Guardian with AI...")
            ai_validation = self.agent_runner.run_agent(
                agent_name="continuity",
                task_prompt=validation_prompt,
                temperature=0.3,  # Low temperature for factual checking
                max_tokens=4096,
                stream=True,
            )
            
            validation_path = self.feedback_dir / f"chapter_{chapter_number:03d}_validation_report.md"
            validation_path.write_text(ai_validation, encoding='utf-8')
            print(f"\n✅ AI validation report saved: {validation_path}")
        else:
            validation_path = self.feedback_dir / f"chapter_{chapter_number:03d}_validation.md"
            validation_path.write_text(validation_prompt, encoding='utf-8')
            print(f"✅ Validation prompt created: {validation_path}")
            print(f"   This checks continuity, timeline, and world consistency.")
    
    def _generate_validation_prompt(self, chapter_number: int, chapter_text: str) -> str:
        """Generate a validation prompt."""
        context = self.state.get_continuity_context(chapter_number)
        
        prompt = f"""# CONTINUITY GUARDIAN PROMPT: Chapter {chapter_number}

## Chapter Text to Validate

```markdown
{chapter_text[:5000]}...
[Chapter continues...]
```

## Current Story State

### Character Positions
"""
        for char_id, location in context['character_locations'].items():
            char = self.state.get_character(char_id)
            if char:
                prompt += f"- **{char.full_name}**: {location or 'Unknown'}\n"
        
        prompt += "\n### Character Emotional States\n"
        for char_id, state in context['character_emotional_states'].items():
            char = self.state.get_character(char_id)
            if char:
                prompt += f"- **{char.full_name}**: {state or 'Unknown'}\n"
        
        prompt += "\n### Active Plot Threads\n"
        for thread_data in context['active_threads']:
            prompt += f"- **{thread_data['name']}**: {thread_data['description'][:80]}...\n"
        
        prompt += f"""
### Previous Chapter Events
[Check against Chapter {chapter_number - 1} events]

## Story Bible Reference
- Genre: {self.state.metadata.get('genre', 'Unknown')}
- World Rules: [Reference story_bible.md]

## Validation Tasks

### Character Continuity
- [ ] Actions align with established personality
- [ ] Knowledge matches what they should know
- [ ] Skills/capabilities remain consistent
- [ ] Relationships reflect prior development

### Timeline Continuity
- [ ] Events occur in logical sequence
- [ ] Time references are consistent
- [ ] Travel times are realistic

### World Consistency
- [ ] Magic/tech rules followed
- [ ] Setting details match prior descriptions

### Plot Continuity
- [ ] Foreshadowing acknowledged or advanced
- [ ] No dropped plot threads (unless intentional)
- [ ] Cause-effect chains intact

## Output Format

```
[CONTINUITY_REPORT]
Chapter: {chapter_number}
Status: [PASS / WARNING / FAIL]

Critical_Issues: [List with suggested fixes]
Warnings: [List with suggested fixes]
New_Facts_Established: [List]
[CONTINUITY_REPORT]
```

---

**Validate this chapter now. Follow your system instructions.**
"""
        return prompt
    
    def approve_chapter(self, chapter_number: int):
        """Mark a chapter as complete and update state."""
        chapter = self.state.get_chapter(chapter_number)
        if not chapter:
            print(f"❌ Chapter {chapter_number} not found.")
            return
        
        chapter.status = 'complete'
        
        # Update character positions/emotions based on state update blocks
        # (In practice, this would parse the state updates from agents)
        
        self.state.save_state()
        
        # Auto-generate chapter summary for future context windows
        if self.chapter_summarizer:
            for suffix in ['_revised', '_draft']:
                ch_path = self.manuscript_dir / f"chapter_{chapter_number:03d}{suffix}.md"
                if ch_path.exists():
                    chapter_text = ch_path.read_text(encoding='utf-8')
                    summaries = self.chapter_summarizer.generate_summary_from_text(chapter_text, chapter_number)
                    print(f"📝 Auto-generated chapter summary for future context:")
                    print(f"   One-liner: {summaries['one_liner']}")
                    break
        
        print(f"✅ Chapter {chapter_number} approved and marked complete!")
        
        # Progress report
        completed = len(self.state.get_completed_chapters())
        total = len(self.state.chapters)
        print(f"\n📊 Progress: {completed}/{total} chapters complete ({completed/total*100:.1f}%)")
    
    # ===== Status and Reporting =====
    
    def status(self):
        """Show project status."""
        print("\n" + "=" * 60)
        print(f"📖 {self.state.metadata.get('title', 'Untitled')}")
        print(f"   Genre: {self.state.metadata.get('genre', 'Unknown')}")
        print(f"   Created: {self.state.metadata.get('created', 'Unknown')}")
        print("=" * 60)
        
        print("\n👥 Characters:", len(self.state.characters))
        print("🔗 Plot Threads:", len(self.state.plot_threads))
        print("   Active:", len(self.state.get_active_plot_threads()))
        
        print("\n📝 Chapters:")
        chapters_by_status = {}
        for ch in self.state.chapters.values():
            status = ch.status
            chapters_by_status[status] = chapters_by_status.get(status, 0) + 1
        
        for status, count in sorted(chapters_by_status.items()):
            icon = {
                'planned': '⚪',
                'drafting': '🟡',
                'drafted': '🟠',
                'editing': '🔵',
                'edited': '🟣',
                'validated': '🟢',
                'complete': '✅'
            }.get(status, '⚪')
            print(f"   {icon} {status.capitalize()}: {count}")
        
        completed = len(self.state.get_completed_chapters())
        total = len(self.state.chapters)
        if total > 0:
            print(f"\n📊 Progress: {completed}/{total} ({completed/total*100:.1f}%)")
        
        print("\n" + "=" * 60)
    
    def export(self, format: str = "markdown"):
        """Export the manuscript."""
        print(f"\n📤 Exporting manuscript as {format}...")
        
        completed_chapters = sorted(
            self.state.get_completed_chapters(),
            key=lambda c: c.number
        )
        
        if format == "markdown":
            output_lines = [
                f"# {self.state.metadata.get('title', 'Untitled')}",
                "",
                f"*{self.state.metadata.get('genre', 'Fiction')}*",
                "",
                "---",
                ""
            ]
            
            for chapter in completed_chapters:
                # Find the chapter file
                for suffix in ['_revised', '_draft']:
                    ch_path = self.manuscript_dir / f"chapter_{chapter.number:03d}{suffix}.md"
                    if ch_path.exists():
                        content = ch_path.read_text(encoding='utf-8')
                        output_lines.append(content)
                        output_lines.append("\n\n---\n\n")
                        break
            
            output_path = self.outputs_dir / f"{self.state.metadata.get('title', 'manuscript').replace(' ', '_')}.md"
            output_path.write_text('\n'.join(output_lines), encoding='utf-8')
            
            print(f"✅ Exported: {output_path}")
        
        # TODO: Add other formats (docx, pdf, etc.)


def main():
    parser = argparse.ArgumentParser(
        description="Novel OS - Multi-Agent Fiction Writing Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s init --title "My Novel" --genre "Thriller"
  %(prog)s character add --name "John Doe" --role protagonist
  %(prog)s plan outline --chapters 32
  %(prog)s plan chapter --number 1
  %(prog)s write --chapter 1
  %(prog)s edit --chapter 1 --mode line
  %(prog)s validate --chapter 1
  %(prog)s approve --chapter 1
  %(prog)s status
  %(prog)s export --format markdown
        """
    )
    
    # Global NIM arguments
    parser.add_argument('--nim-key', default='', help='NVIDIA NIM API key (or set NVIDIA_NIM_API_KEY env var)')
    parser.add_argument('--nim-model', default='', help='NIM model to use (default: llama-3.1-70b)')
    parser.add_argument('--chunk-limit', type=int, default=None, help='Words per section before chunking (e.g. 2000)')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # NIM test command
    nim_parser = subparsers.add_parser('nim', help='Test NIM API connection')
    nim_parser.add_argument('--list-models', action='store_true', help='List available NIM models')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize a new project')
    init_parser.add_argument('--title', required=True, help='Novel title')
    init_parser.add_argument('--genre', required=True, help='Primary genre')
    init_parser.add_argument('--author', default='', help='Author name')
    
    # Character commands
    char_parser = subparsers.add_parser('character', help='Character management')
    char_subparsers = char_parser.add_subparsers(dest='char_command')
    
    char_add = char_subparsers.add_parser('add', help='Add a character')
    char_add.add_argument('--name', required=True, help='Character full name')
    char_add.add_argument('--role', required=True, choices=['protagonist', 'antagonist', 'supporting', 'minor'])
    
    char_list = char_subparsers.add_parser('list', help='List characters')
    
    # Plot commands
    plot_parser = subparsers.add_parser('plot', help='Plot thread management')
    plot_subparsers = plot_parser.add_subparsers(dest='plot_command')
    
    plot_add = plot_subparsers.add_parser('add', help='Add a plot thread')
    plot_add.add_argument('--name', required=True, help='Thread name')
    plot_add.add_argument('--description', required=True, help='Thread description')
    plot_add.add_argument('--type', default='main', choices=['main', 'subplot', 'character_arc', 'mystery'])
    plot_add.add_argument('--priority', type=int, default=3, help='Priority 1-5')
    
    plot_list = plot_subparsers.add_parser('list', help='List plot threads')
    
    # Plan commands
    plan_parser = subparsers.add_parser('plan', help='Planning phase')
    plan_subparsers = plan_parser.add_subparsers(dest='plan_command')
    
    plan_outline = plan_subparsers.add_parser('outline', help='Create story outline')
    plan_outline.add_argument('--chapters', type=int, default=32, help='Number of chapters')
    plan_outline.add_argument('--words', type=int, default=80000, help='Target word count')
    
    plan_chapter = plan_subparsers.add_parser('chapter', help='Plan specific chapter')
    plan_chapter.add_argument('--number', type=int, required=True, help='Chapter number')
    plan_chapter.add_argument('--summary', default='', help='Chapter summary')
    plan_chapter.add_argument('--pov', default='', help='POV character')
    
    # Write command
    write_parser = subparsers.add_parser('write', help='Writing phase')
    write_parser.add_argument('--chapter', type=int, required=True, help='Chapter number')
    write_parser.add_argument('--draft-file', default='', help='Path to draft file')
    
    # Edit command
    edit_parser = subparsers.add_parser('edit', help='Editing phase')
    edit_parser.add_argument('--chapter', type=int, required=True, help='Chapter number')
    edit_parser.add_argument('--mode', default='line', 
                            choices=['line', 'developmental', 'pacing', 'dialogue', 'tension'],
                            help='Editing mode')
    edit_parser.add_argument('--edited-file', default='', help='Path to edited file')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validation phase')
    validate_parser.add_argument('--chapter', type=int, required=True, help='Chapter number')
    
    # Approve command
    approve_parser = subparsers.add_parser('approve', help='Approve chapter')
    approve_parser.add_argument('--chapter', type=int, required=True, help='Chapter number')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show project status')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export manuscript')
    export_parser.add_argument('--format', default='markdown', choices=['markdown', 'docx'],
                              help='Export format')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Resolve NIM API key from args or environment
    nim_key = args.nim_key or os.environ.get('NVIDIA_NIM_API_KEY', '')
    
    # Handle NIM test command before initializing orchestrator
    if args.command == 'nim':
        if not NIM_AVAILABLE:
            print("❌ NIM client not available. Check that nim_client.py exists in core/.")
            return
        if not nim_key:
            print("❌ NIM API key required. Use --nim-key or set NVIDIA_NIM_API_KEY env var.")
            return
        client = NIMClient(api_key=nim_key, default_model=args.nim_model or 'llama-3.1-70b')
        if hasattr(args, 'list_models') and args.list_models:
            print("📋 Pre-configured NIM Models:")
            for short, full in NIM_MODELS.items():
                print(f"  • {short:20s} → {full}")
            print("\n📋 Fetching available models from API...")
            models = client.list_available_models()
            for m in models:
                print(f"  • {m.get('id', 'unknown')}")
        else:
            client.test_connection()
        return
    
    # Initialize orchestrator (with optional NIM)
    orchestrator = NovelOrchestrator(nim_api_key=nim_key, nim_model=args.nim_model, chunk_limit=args.chunk_limit)
    
    # Route commands
    if args.command == 'init':
        orchestrator.init_project(args.title, args.genre, args.author)
    
    elif args.command == 'character':
        if args.char_command == 'add':
            orchestrator.add_character(args.name, args.role)
        elif args.char_command == 'list':
            orchestrator.list_characters()
        else:
            char_parser.print_help()
    
    elif args.command == 'plot':
        if args.plot_command == 'add':
            orchestrator.add_plot_thread(args.name, args.description, args.type, args.priority)
        elif args.plot_command == 'list':
            orchestrator.list_plot_threads()
        else:
            plot_parser.print_help()
    
    elif args.command == 'plan':
        if args.plan_command == 'outline':
            orchestrator.plan_outline(args.chapters, args.words)
        elif args.plan_command == 'chapter':
            orchestrator.plan_chapter(args.number, args.summary, args.pov)
        else:
            plan_parser.print_help()
    
    elif args.command == 'write':
        if args.draft_file:
            orchestrator.submit_draft(args.chapter, args.draft_file)
        else:
            orchestrator.write_chapter(args.chapter)
    
    elif args.command == 'edit':
        if args.edited_file:
            orchestrator.submit_edit(args.chapter, args.edited_file)
        else:
            orchestrator.edit_chapter(args.chapter, args.mode)
    
    elif args.command == 'validate':
        orchestrator.validate_chapter(args.chapter)
    
    elif args.command == 'approve':
        orchestrator.approve_chapter(args.chapter)
    
    elif args.command == 'status':
        orchestrator.status()
    
    elif args.command == 'export':
        orchestrator.export(args.format)


if __name__ == '__main__':
    main()
