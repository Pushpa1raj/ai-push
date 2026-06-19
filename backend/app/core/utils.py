import string

def generate_conversation_title(text: str) -> str:
    prefixes = [
        "how do i ", "how to ", "how can i ",
        "explain ", "explain to me ",
        "what is ", "what are ", "whats ", "what's ",
        "tell me about ", "tell me ",
        "can you ", "could you ", "please ",
        "write a ", "write an ", "write ",
        "create a ", "create an ", "create ",
        "help me with ", "help me "
    ]
    
    text = text.strip()
    
    # Strip prefix
    lower_text = text.lower()
    for prefix in prefixes:
        if lower_text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
            
    # Remove punctuation
    translator = str.maketrans('', '', string.punctuation)
    text = text.translate(translator)
    
    # Title case logic that preserves existing capital letters
    words = text.split()
    title_words = []
    
    # Stop words that should be lowercase in title case (unless they are the first word)
    stop_words = {"a", "an", "the", "and", "but", "or", "for", "nor", "on", "at", "to", "from", "by", "in", "of"}
    
    for i, w in enumerate(words):
        if i > 0 and w.lower() in stop_words and w.islower():
            title_words.append(w.lower())
        else:
            if w.islower():
                title_words.append(w.capitalize())
            else:
                title_words.append(w[0].upper() + w[1:])
                
    text = " ".join(title_words)
    
    # Truncate to maximum 40 characters
    if len(text) > 40:
        text = text[:40].rsplit(' ', 1)[0]
        if not text:
            text = text[:40]
            
    return text
