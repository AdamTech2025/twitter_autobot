import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import logging

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

logger = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

class LightweightCrew:
    """Lightweight replacement for CrewAI using direct OpenAI API calls"""
    
    def __init__(self):
        if not client:
            logger.warning("OpenAI API key not found. Content generation will use fallback method.")

    def kickoff(self, user_topics=None):
        """Generate content using OpenAI API instead of CrewAI"""
        try:
            if not client:
                return self._fallback_content_generation(user_topics)
            
            # Create a prompt based on user topics
            topics_text = ", ".join(user_topics) if user_topics else "AI, technology, business"
            
            prompt = f"""
            You are a professional social media content creator. Create ONE engaging tweet about trending topics related to: {topics_text}

            Requirements:
            - Maximum 280 characters
            - Professional and informative tone
            - Include relevant hashtags
            - Make it engaging and thought-provoking
            - Focus on current trends and insights

            Return only the tweet text, nothing else.
            """
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional social media content creator specializing in tech and business content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            generated_tweet = response.choices[0].message.content.strip()
            logger.info(f"Generated tweet using OpenAI: {generated_tweet}")
            return generated_tweet
            
        except Exception as e:
            logger.error(f"Error generating content with OpenAI: {e}")
            return self._fallback_content_generation(user_topics)
    
    def _fallback_content_generation(self, user_topics=None):
        """Fallback content generation when OpenAI is not available"""
        if user_topics:
            topics_str = ", ".join(user_topics[:3])
            templates = [
                f"Exploring the latest developments in {topics_str}. What trends are you seeing? #Innovation #Tech",
                f"The future of {topics_str} is evolving rapidly. Share your insights! #TechTrends #Future",
                f"Key insights on {topics_str} that every professional should know. What's your take? #Business #Growth",
                f"Breaking down the impact of {topics_str} on modern business. Thoughts? #Technology #Strategy"
            ]
            import random
            return random.choice(templates)
        else:
            return "Staying ahead of the curve with the latest tech innovations. What's catching your attention today? #AI #Tech #Innovation"

# Create global crew instance
crew = LightweightCrew()

# Test function
def test_content_generation():
    """Test the content generation"""
    test_topics = ["AI", "Machine Learning", "Business"]
    result = crew.kickoff(test_topics)
    print(f"Generated content: {result}")
    return result

if __name__ == "__main__":
    print("✅ Lightweight crew.py loaded successfully.")
    test_content_generation()
