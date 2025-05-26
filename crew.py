import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI
import litellm
from litellm import completion

# Load environment variables from ../.env
dotenv_path = os.path.join(os.path.dirname(__file__), '../.env')
load_dotenv(dotenv_path=dotenv_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class GeminiWrapper:
    def __init__(self):
        self.model = "gemini/gemini-1.5-flash"
        self.api_key = GOOGLE_API_KEY
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables.")

    def chat_completion_create(self, messages):
        response = completion(
            model=self.model,
            messages=messages,
            api_key=self.api_key
        )
        return response.choices[0].message.content

    def __call__(self, messages, **kwargs):
        return self.chat_completion_create(messages)

llm = GeminiWrapper() if GOOGLE_API_KEY else None

# === Agents (focused on ONE tweet only) ===
trending_agent = Agent(
    role="Trending Topic Identifier",
    goal="Identify one trending and relevant topic from X.com about AI, business, finance, deep tech, or education.",
    backstory="You're a trendspotter who knows what's hot right now.",
    verbose=True,
    allow_delegation=False,
    llm=llm
)

content_generator_agent = Agent(
    role="Tweet Generator",
    goal="Write one high-quality, engaging, and professional tweet based on a trending topic.",
    backstory="You're a top-notch copywriter skilled at creating viral tweets.",
    verbose=True,
    allow_delegation=False,
    llm=llm
)

humanizer_agent = Agent(
    role="Tweet Humanizer",
    goal="Make the tweet sound more natural and human while keeping it informative and professional.",
    backstory="You're a social media whisperer who makes posts relatable.",
    verbose=True,
    allow_delegation=False,
    llm=llm
)

validator_agent = Agent(
    role="Tweet Validator",
    goal="Check the tweet for tone, clarity, and compliance with X.com's guidelines.",
    backstory="You're a quality gatekeeper who ensures only perfect content goes out.",
    verbose=True,
    allow_delegation=False,
    llm=llm
)

# === Tasks (one tweet workflow) ===
trending_task = Task(
    description="Identify one hot trending topic from X.com related to AI, business, finance, deep tech, or education.",
    agent=trending_agent,
    expected_output="A single trending topic title or short description."
)

generation_task = Task(
    description="Write one engaging, insightful tweet for the trending topic.",
    agent=content_generator_agent,
    expected_output="A single tweet (280 characters max).",
    context=[trending_task]
)

humanize_task = Task(
    description="Make the tweet more human, clear, and engaging without losing factual accuracy.",
    agent=humanizer_agent,
    expected_output="A single improved tweet.",
    context=[generation_task]
)

validation_task = Task(
    description="Validate the tweet for tone, accuracy, and X.com policy compliance.",
    agent=validator_agent,
    expected_output="One final approved tweet.",
    context=[humanize_task]
)

# === Crew Setup ===
crew = Crew(
    agents=[
        trending_agent,
        content_generator_agent,
        humanizer_agent,
        validator_agent
    ],
    tasks=[
        trending_task,
        generation_task,
        humanize_task,
        validation_task
    ],
    process=Process.sequential,
    verbose=True,
    max_iterations=5
)

# === Run Crew ===
if __name__ == "__main__":
    final_tweet = crew.kickoff()
    print("\n✅ FINAL APPROVED TWEET:\n")
    print(final_tweet)

print("✅ crew.py loaded successfully.")
