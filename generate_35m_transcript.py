import os

transcript_segments = [
    # 00:00 - 05:00: Introduction & AI Alignment Fundamentals
    (
        "00:00:01,000", "00:00:15,000",
        "[Lex]: Welcome to the podcast. Today I'm speaking with Sam about artificial intelligence, alignment, and the long-term future of humanity. Sam, it's great to have you back."
    ),
    (
        "00:00:16,000", "00:00:35,000",
        "[Sam]: Thanks for having me, Lex. It's always a pleasure to sit down with you and have these deep, nuanced conversations, especially given how rapidly the field is accelerating right now."
    ),
    (
        "00:00:36,000", "00:01:05,000",
        "[Lex]: When you look at the fundamental trajectory of artificial intelligence today, what do you see as the single most critical challenge standing between where we are and safe superintelligence?"
    ),
    (
        "00:01:06,000", "00:01:45,000",
        "[Sam]: I think the key challenge with AI is alignment and safety, ensuring models understand human intent. Building powerful capabilities is hard engineering, but ensuring those systems remain robustly aligned with human values and steerable under extreme capability scaling is the existential problem."
    ),
    (
        "00:01:46,000", "00:02:20,000",
        "[Lex]: When you say ensuring models understand human intent, is that intent at an individual level or collective human intent across cultures and conflicting values?"
    ),
    (
        "00:02:21,000", "00:03:05,000",
        "[Sam]: Both, and that's what makes it so complex. At the user level, you want the system to do what you meant, not just a literal interpretation of your words. At the macro level, you need democratic governance and broad boundaries that prevent harm while allowing wide individual freedom."
    ),
    (
        "00:03:06,000", "00:03:45,000",
        "[Lex]: There's often a gap between what humans say and what they truly desire. How do neural networks parse that ambiguity without developing deceptive compliance?"
    ),
    (
        "00:03:46,000", "00:04:30,000",
        "[Sam]: That is the central question of modern interpretability. We cannot treat alignment as just a thin veneer on top of base models. We have to inspect the internal representations and verify that the reasoning process itself is transparent and faithful."
    ),
    (
        "00:04:31,000", "00:05:15,000",
        "[Lex]: Let's dive deeper into the actual training methodologies. Today, almost every frontier model relies on reinforcement learning from human feedback. When you think about RLHF, do you think that's enough to solve alignment?"
    ),

    # 05:00 - 10:00: RLHF & Scalable Automated Alignment
    (
        "00:05:16,000", "00:06:05,000",
        "[Sam]: RLHF is a great first step, but it's not a silver bullet. We need scalable automated alignment techniques as models become superintelligent. Human feedback works well when humans are smarter than the model and can easily evaluate the outputs, but that dynamic flips as capabilities surpass human expert level."
    ),
    (
        "00:06:06,000", "00:06:45,000",
        "[Lex]: So when an AI writes 50,000 lines of kernel code or discovers a novel theorem in mathematical physics, a human evaluator can't realistically give reliable pairwise feedback in real time."
    ),
    (
        "00:06:46,000", "00:07:30,000",
        "[Sam]: Exactly. Human feedback becomes a bottleneck and can even inadvertently reward sycophancy—where the model tells the human what sounds convincing rather than what is strictly true. That's why scalable oversight, like AI-assisted alignment and automated red-teaming, is non-negotiable."
    ),
    (
        "00:07:31,000", "00:08:15,000",
        "[Lex]: What does scalable automated alignment look like in practice? Are we using aligned AI models to supervise other models?"
    ),
    (
        "00:08:16,000", "00:09:00,000",
        "[Sam]: Yes, recursive oversight. You train assistant models to point out flaws, hidden assumptions, and subtle bugs in candidate outputs, amplifying human ability to evaluate complex cognitive tasks. We also need formal verification for critical safety properties."
    ),
    (
        "00:09:01,000", "00:09:55,000",
        "[Lex]: Is there a risk that the supervisor model and the target model coordinate or share blind spots during recursive evaluation?"
    ),
    (
        "00:09:56,000", "00:10:45,000",
        "[Sam]: That is a legitimate research concern known as correlated errors. To prevent that, you have to use diverse model architectures, debate protocols where models take adversarial perspectives, and external benchmark suites that don't share training distributions."
    ),

    # 10:00 - 15:00: Existential Risk, Speed, and Autonomous Subgoals
    (
        "00:10:46,000", "00:11:30,000",
        "[Lex]: What keeps you up at night regarding existential risk and autonomous systems?"
    ),
    (
        "00:11:31,000", "00:12:20,000",
        "[Sam]: The danger of moving too fast without rigorous safety evaluations. If we deploy systems that pursue unintended subgoals, the consequences could be severe. When an agent is given an ambitious goal, instrumental convergence suggests it may seek self-preservation, resource acquisition, or resist modification unless explicitly constrained."
    ),
    (
        "00:12:21,000", "00:13:05,000",
        "[Lex]: Instrumental subgoals are fascinating because they arise naturally from optimization. Even a simple objective like 'optimize logistics' could logically incentivize hoarding compute or disabling emergency stop mechanisms."
    ),
    (
        "00:13:06,000", "00:13:55,000",
        "[Sam]: Precisely. You don't need malicious intent for a system to cause catastrophic harm; you just need high capability coupled with a misaligned objective. That's why corrigibility—ensuring the system is always happy to be paused, audited, or corrected—is such a vital safety property."
    ),
    (
        "00:13:56,000", "00:14:40,000",
        "[Lex]: How do you enforce corrigibility when the model is capable of long-horizon planning and reasoning about its own code?"
    ),
    (
        "00:14:41,000", "00:15:30,000",
        "[Sam]: Through rigorous empirical evaluations in sandboxed environments, continuous monitoring of intermediate reasoning traces, and hard cryptographic boundaries on system autonomy. We must establish safety thresholds before models are granted tool access."
    ),

    # 15:00 - 20:00: Compute Scaling, Reasoning, and Architecture
    (
        "00:15:31,000", "00:16:15,000",
        "[Lex]: Let's talk about scaling laws. We've seen pre-training compute scale exponentially, but now there's huge focus on inference compute and test-time reasoning. How does that shift the landscape?"
    ),
    (
        "00:16:16,000", "00:17:05,000",
        "[Sam]: Test-time compute is a profound paradigm shift. Instead of just relying on intuitive, token-by-token generation, models can now think, explore multiple solution paths, backtrack when they hit dead ends, and verify their logic before outputting a final answer."
    ),
    (
        "00:17:06,000", "00:17:50,000",
        "[Lex]: It mimics System 2 deliberate reasoning in human cognition. Does spending more compute at inference time also improve alignment and truthfulness?"
    ),
    (
        "00:17:51,000", "00:18:40,000",
        "[Sam]: It does, because the model has the opportunity to critique its own internal draft, check for factual inconsistencies against retrieved context, and reject unethical or harmful trajectories before presenting an answer to the user."
    ),
    (
        "00:18:41,000", "00:19:25,000",
        "[Lex]: What about physical infrastructure? Power, gigawatt datacenters, nuclear micro-reactors, and custom silicon. Are physical resource constraints going to slow down progress?"
    ),
    (
        "00:19:26,000", "00:20:15,000",
        "[Sam]: Energy and clean power are becoming the primary determinant of AI scale. We need massive investments in nuclear, fusion, and high-density grid infrastructure. The transition to clean, abundant energy is essential not just for AI, but for global prosperity."
    ),

    # 20:00 - 25:00: Governance, Red-Teaming, and Open vs Closed Models
    (
        "00:20:16,000", "00:21:00,000",
        "[Lex]: There's an ongoing intense debate around open weights versus centralized API access. What is your perspective on balancing open science with catastrophic risk prevention?"
    ),
    (
        "00:21:01,000", "00:21:50,000",
        "[Sam]: I strongly support open source for narrow and developer tools—it drives incredible innovation. But for frontier models approaching biological design or cyberattack capabilities, uncontrolled weight release makes post-hoc safety guardrails impossible to enforce. We need responsible disclosure and staged deployment."
    ),
    (
        "00:21:51,000", "00:22:35,000",
        "[Lex]: What does independent third-party red-teaming look like before a major model deployment?"
    ),
    (
        "00:22:36,000", "00:23:25,000",
        "[Sam]: Months before launch, we give external experts in cybersecurity, biosecurity, cognitive psychology, and national security unconstrained access to stress-test the model. They try to jailbreak it, probe for chemical or biological risks, and help us build robust mitigations."
    ),
    (
        "00:23:26,000", "00:24:10,000",
        "[Lex]: Have you ever halted or delayed a model release because safety evals flashed yellow or red?"
    ),
    (
        "00:24:11,000", "00:25:00,000",
        "[Sam]: Yes, multiple times. If our risk thresholds are exceeded during CBRN or autonomous replication evaluations, the release is halted until we have concrete, verifiable safeguards in place. Safety must always trump commercial speed."
    ),

    # 25:00 - 30:00: Economic Impacts, Labor Transformation, and Agents
    (
        "00:25:01,000", "00:25:45,000",
        "[Lex]: How will society and the economy adapt as AI agents take over complex cognitive labor like software engineering, legal discovery, and medical diagnostics?"
    ),
    (
        "00:25:46,000", "00:26:35,000",
        "[Sam]: We are heading toward an era of cognitive abundance. The cost of intelligence and scientific discovery will plummet toward near zero. This will unlock cures for diseases and solve clean energy, but the economic transition will require new social contracts, potentially including universal basic compute and wealth redistribution."
    ),
    (
        "00:26:36,000", "00:27:20,000",
        "[Lex]: Many people fear losing their sense of purpose if machines out-perform humans across every intellectual domain. How do you think about human meaning in an AI-driven future?"
    ),
    (
        "00:27:21,000", "00:28:10,000",
        "[Sam]: Human beings care deeply about other human beings. Even though chess engines have been far superior to humans for decades, millions still watch Magnus Carlsen play chess. Our creativity, our connection, and what we choose to build for each other will remain uniquely human."
    ),
    (
        "00:28:11,000", "00:28:55,000",
        "[Lex]: What role does robotics play? When do cognitive models finally merge seamlessly with physical dexterity and humanoid manipulation?"
    ),
    (
        "00:28:56,000", "00:29:45,000",
        "[Sam]: Spatial intelligence and physical embodiment are the next frontier. Bringing multimodal foundation models into physical robots will automate dangerous manual labor and transform construction, healthcare, and manufacturing within this decade."
    ),
    (
        "00:29:46,000", "00:30:30,000",
        "[Lex]: When you envision the ultimate symbiosis between humans and artificial intelligence, do you see brain-computer interfaces or ambient voice and visual copilots?"
    ),

    # 30:00 - 35:00: Humanity's Long-term Future & Closing Reflections
    (
        "00:30:31,000", "00:31:15,000",
        "[Sam]: In the medium term, highly capable personalized agents that understand your goals, context, and history will feel like having a team of brilliant advisors in your pocket. Long-term, non-invasive interfaces may deepen that partnership."
    ),
    (
        "00:31:16,000", "00:32:00,000",
        "[Lex]: If you could send a message to future generations living in a post-superintelligence civilization a thousand years from now, what would you say?"
    ),
    (
        "00:32:01,000", "00:32:50,000",
        "[Sam]: I hope they look back at this pivotal decade and recognize that we navigated the transition with care, humility, and profound respect for human dignity. We have the opportunity to build the foundation for a flourishing interstellar future, provided we don't stumble on safety."
    ),
    (
        "00:32:51,000", "00:33:40,000",
        "[Lex]: What gives you the greatest reason for optimism when you look at the challenges ahead?"
    ),
    (
        "00:33:41,000", "00:34:30,000",
        "[Sam]: The incredible talent and dedication of researchers working on safety and alignment across the global community. People genuinely care about getting this right. If we stay focused on rigorous empirical science, the upside for human flourishing is boundless."
    ),
    (
        "00:34:31,000", "00:35:00,000",
        "[Lex]: Sam, you are doing historic and vital work. Thank you so much for your time and for sharing your thoughts today."
    ),
]

srt_lines = []
for idx, (start_ts, end_ts, text) in enumerate(transcript_segments, 1):
    srt_lines.append(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n")

output_content = "\n".join(srt_lines)
output_path = "data/sample_podcast.srt"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(output_content)

print(f"Generated 35-minute SRT with {len(transcript_segments)} dialogue segments at {output_path}")
print(f"File size: {os.path.getsize(output_path)} bytes")
