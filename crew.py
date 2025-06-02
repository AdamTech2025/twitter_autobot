import os
import json
from dotenv import load_dotenv
import logging

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

logger = logging.getLogger(__name__)

# Import llm_services for OpenRouter support
try:
    from llm_services import get_service as get_llm_service
    llm_service = get_llm_service()
    # Configure OpenRouter for tweet generation
    llm_service.set_temperature(0.7)  # More creative for social media content
    logger.info("Successfully imported and configured llm_services for OpenRouter support")
except ImportError as e:
    logger.warning(f"Failed to import llm_services: {e}")
    llm_service = None
except ValueError as e:
    if "OpenRouter API key not found" in str(e):
        logger.warning("OpenRouter API key not found in environment variables. Add OPENROUTER_API_KEY to .env file to enable OpenRouter support.")
    else:
        logger.warning(f"Error initializing llm_services: {e}")
    llm_service = None
except Exception as e:
    logger.warning(f"Error configuring llm_services: {e}")
    llm_service = None

class LightweightCrew:
    """Lightweight content generator using OpenRouter via llm_services"""
    
    def __init__(self):
        self.llm_service = llm_service

    def kickoff(self, user_topics=None):
        """Generate content using OpenRouter LLM service"""
        # Create a prompt based on user topics
        topics_text = ", ".join(user_topics) if user_topics else "AI, technology, business"
        
        prompt = f"""You are a professional social media content creator. Create ONE engaging tweet about trending topics related to: {topics_text}

Requirements:
- Maximum 280 characters (this is critical - count characters carefully)
- Professional and informative tone
- NO hashtags at all
- Make it engaging and thought-provoking
- Focus on current trends and insights
- Write as a statement, question, or insight
- Keep it conversational and natural

Return only the tweet text, nothing else. Do not include any hashtags."""
        
        # Use OpenRouter via llm_services
        if self.llm_service:
            try:
                generated_tweet = self.llm_service.generate_response(prompt)
                
                # Ensure character limit
                if len(generated_tweet) > 280:
                    generated_tweet = generated_tweet[:277] + "..."
                
                logger.info(f"Generated tweet using OpenRouter ({len(generated_tweet)} chars): {generated_tweet}")
                return generated_tweet
                
            except Exception as e:
                logger.error(f"Error generating content with OpenRouter: {e}")
                logger.info("Falling back to manual templates...")
        
        # Simple fallback only when OpenRouter is not available
        logger.info("Using fallback content generation")
        return self._fallback_content_generation(user_topics)
    
    def _fallback_content_generation(self, user_topics=None):
        """Simple fallback content generation when OpenRouter is not available"""
        if user_topics:
            topics_str = ", ".join(user_topics[:3])
            templates = [
                f"Exploring the latest developments in {topics_str}. What trends are you seeing in your industry?",
                f"The future of {topics_str} is evolving rapidly. How are you adapting to these changes?",
                f"Key insights on {topics_str} that every professional should know. What's your perspective?",
                f"Breaking down the impact of {topics_str} on modern business. What patterns do you notice?",
                f"The intersection of {topics_str} is creating new opportunities. Where do you see the biggest potential?",
                f"Understanding {topics_str} has become essential for staying competitive. What's your experience?"
            ]
            import random
            selected_template = random.choice(templates)
            
            # Ensure character limit
            if len(selected_template) > 280:
                selected_template = selected_template[:277] + "..."
                
            return selected_template
        else:
            fallback_content = "Staying ahead of the curve with the latest tech innovations. What's catching your attention today?"
            return fallback_content

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
