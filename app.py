import gradio as gr
import asyncio
from typing import List, Dict, Any, Tuple, Generator
from beeai import Bee
from huggingface_hub import InferenceClient
import logging
from datetime import datetime
import pytz
import pandas as pd
from functools import partial

# Set up logging with a higher level
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='app.log',
                    filemode='w')

# Global variable to track the current page
current_page = 1
total_pages = 1

async def fetch_conversations(api_key: str, page: int = 1) -> Dict[str, Any]:
    bee = Bee(api_key)
    logging.info(f"Fetching conversations for user 'me', page {page}")
    conversations = await bee.get_conversations("me", page=page, limit=15)
    return conversations

def format_end_time(end_time: str) -> str:
    utc_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    user_timezone = pytz.timezone('US/Pacific')  # TODO: Replace with actual user timezone
    local_time = utc_time.astimezone(user_timezone)
    timezone_abbr = local_time.strftime('%Z')
    return f"{local_time.strftime('%I:%M %p')} {timezone_abbr}"

async def fetch_conversation(api_key: str, conversation_id: int) -> Dict[str, Any]:
    bee = Bee(api_key)
    try:
        logging.info(f"Fetching conversation with ID: {conversation_id}")
        full_conversation = await bee.get_conversation("me", conversation_id)
        logging.debug(f"Raw conversation data: {full_conversation}")
        return full_conversation
    except Exception as e:
        logging.error(f"Error fetching conversation {conversation_id}: {str(e)}")
        return {"error": f"Failed to fetch conversation: {str(e)}"}

def format_conversation(data: Dict[str, Any]) -> str:
    try:
        conversation = data.get("conversation", {})
        logging.debug(f"Conversation keys: {conversation.keys()}")
        formatted = f"# Conversation [{conversation['id']}] "
        # Format start_time and end_time
        start_time = conversation.get('start_time')
        end_time = conversation.get('end_time')
        if start_time and end_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            pacific_tz = pytz.timezone('US/Pacific')
            start_pacific = start_dt.astimezone(pacific_tz)
            end_pacific = end_dt.astimezone(pacific_tz)
            
            if start_pacific.date() == end_pacific.date():
                formatted += f"{start_pacific.strftime('%I:%M %p')} - {end_pacific.strftime('%I:%M %p')} PT\n\n"
            else:
                formatted += f"\n\n**Start**: {start_pacific.strftime('%Y-%m-%d %I:%M %p')} PT\n"
                formatted += f"**End**: {end_pacific.strftime('%Y-%m-%d %I:%M %p')} PT\n"
        elif start_time:
            start_time_formatted = format_end_time(start_time)
            formatted += f"**Start**: {start_time_formatted}\n"
        elif end_time:
            end_time_formatted = format_end_time(end_time)
            formatted += f"**End**: {end_time_formatted}\n"
        
        # Display short_summary nicely
        if 'short_summary' in conversation:
            formatted += f"\n## Short Summary\n\n{conversation['short_summary']}\n"

        formatted += "\n"  # Add a newline for better readability

        formatted += f"\n{conversation['summary']}"
        # for key in ['summary']: #, 'short_summary', 'state', 'created_at', 'updated_at']:
        #     if key in conversation:
        #         formatted += f"**{key}**: {conversation[key]}\n"
        
        if 'transcriptions' in conversation and conversation['transcriptions']:
            formatted += "\n\n## Transcriptions\n\n"
            last_timestamp = None
            for utterance in conversation['transcriptions'][0].get('utterances', []):
                current_timestamp = utterance.get('spoken_at')
                speaker = utterance.get('speaker')
                text = utterance.get('text')
                
                if last_timestamp is not None:
                    time_diff = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00')) - datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
                    if time_diff.total_seconds() > 300:  # More than 5 minutes
                        local_time = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00')).astimezone().strftime('%I:%M %p')
                        formatted += f"[{local_time}]\n\n"
                
                formatted += f"Speaker **[{speaker}](https://kagi.com/search?q={current_timestamp})**: {text}\n\n"
                last_timestamp = current_timestamp
        
        return formatted
    except Exception as e:
        logging.error(f"Error formatting conversation: {str(e)}")
        return f"Error formatting conversation: {str(e)}\n\nRaw data: {conversation}"

def format_duration(start_time: str, end_time: str) -> str:
    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    duration = end_dt - start_dt
    return f"{duration.total_seconds() // 3600:.0f}h {((duration.total_seconds() % 3600) // 60):.0f}m"

async def list_conversations(api_key: str) -> Tuple[pd.DataFrame, str, int, int]:
    global current_page, total_pages
    conversations_data = await fetch_conversations(api_key, current_page)
    conversations = conversations_data.get("conversations", [])
    total_pages = conversations_data.get("totalPages", 1)
    df = pd.DataFrame([
        {
            "ID": c['id'],
            "Duration": format_duration(c['start_time'], c['end_time']) if c['start_time'] and c['end_time'] else "",
            "Summary": ' '.join(c['short_summary'].split()[1:21]) + "..." if c['short_summary'] else "",
            "End Time": format_end_time(c['end_time']) if c['end_time'] else "",
        }
        for c in conversations
    ])
    df = df[["ID", "End Time", "Duration", "Summary"]]  # Reorder columns to ensure ID is first
    info = f"Page {current_page} of {total_pages}"
    return df, info, current_page, total_pages

async def display_conversation(api_key: str, conversation_id: int) -> str:
    full_conversation = await fetch_conversation(api_key, conversation_id)
    if "error" in full_conversation:
        logging.error(f"Error in full_conversation: {full_conversation['error']}")
        return full_conversation["error"]
    formatted_conversation = format_conversation(full_conversation)
    return formatted_conversation

async def delete_conversation(api_key: str, conversation_id: int) -> str:
    bee = Bee(api_key)
    try:
        await bee.delete_conversation("me", conversation_id)
        return f"Conversation {conversation_id} deleted successfully."
    except Exception as e:
        logging.error(f"Error deleting conversation {conversation_id}: {str(e)}")
        return f"Failed to delete conversation: {str(e)}"

client = InferenceClient("HuggingFaceH4/zephyr-7b-beta")

def respond(
    message: str,
    history: List[Tuple[str, str]],
    system_message: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    conversation_context: str
) -> Generator[str, None, None]:
    messages = [
        {"role": "system", "content": system_message},
        {"role": "system", "content": f"Here's the context of the conversation: {conversation_context}"}
    ]

    for human, assistant in history:
        messages.append({"role": "user", "content": human})
        messages.append({"role": "assistant", "content": assistant})

    messages.append({"role": "user", "content": message})

    response = ""

    for message in client.chat_completion(
        messages,
        max_tokens=max_tokens,
        stream=True,
        temperature=temperature,
        top_p=top_p,
    ):
        token = message.choices[0].delta.content
        response += token
        yield response

# Add this new function
def get_selected_conversation_id(table_data):
    if table_data and len(table_data) > 0:
        # Assuming the ID is in the first column
        return table_data[0][0]
    return None

async def delete_selected_conversation(api_key: str, conversation_id: int):
    if not api_key or not conversation_id:
        return "No conversation selected or API key missing", None, None, gr.update(visible=False), ""
    
    logging.info(f"Deleting conversation with ID: {conversation_id}")
    
    try:
        result = await delete_conversation(api_key, conversation_id)
        df, info, current_page, total_pages = await list_conversations(api_key)
        return result, df, info, gr.update(visible=False), ""
    except Exception as e:
        error_message = f"Error deleting conversation: {str(e)}"
        logging.error(error_message)
        return error_message, None, None, gr.update(visible=False), ""

with gr.Blocks() as demo:
    gr.Markdown("# Bee AI Conversation Viewer and Chat")
    
    with gr.Row():
        with gr.Column(scale=1):
            api_key = gr.Textbox(label="Enter your Bee API Key", type="password")
            load_button = gr.Button("Load Conversations")
            conversation_table = gr.Dataframe(
                label="Select a conversation (CLICK ON THE ID!!!)",
                interactive=True,
                row_count=10  # Adjust this number to approximate the desired height
            )
            info_text = gr.Textbox(label="Info", interactive=False)
            prev_page = gr.Button("Previous Page")
            next_page = gr.Button("Next Page")
        
        with gr.Column(scale=2):
            conversation_details = gr.Markdown(
                label="Conversation Details",
                value="Enter your Bee API Key, click 'Load Conversations', then select a conversation to view details here."
            )
            delete_button = gr.Button("Delete Conversation", visible=False)
    
    selected_conversation_id = gr.State(None)

    async def load_conversations(api_key):
        try:
            df, info, current_page, total_pages = await list_conversations(api_key)
            prev_disabled = current_page == 1
            next_disabled = current_page == total_pages
            return df, info, gr.update(visible=True), gr.update(interactive=not prev_disabled), gr.update(interactive=not next_disabled)
        except Exception as e:
            error_message = f"Error loading conversations: {str(e)}"
            logging.error(error_message)
            return None, error_message, gr.update(visible=False), gr.update(interactive=False), gr.update(interactive=False)

    load_button.click(load_conversations, inputs=[api_key], outputs=[conversation_table, info_text, delete_button, prev_page, next_page])

    async def update_conversation(api_key, evt: gr.SelectData):
        try:
            logging.info(f"SelectData event: index={evt.index}, value={evt.value}")
            conversation_id = int(evt.value)
            logging.info(f"Updating conversation with ID: {conversation_id}")
            
            # Return a loading message immediately
            yield gr.update(value="Loading conversation details...", visible=True), gr.update(visible=False), None
            
            # Fetch and format the conversation
            formatted_conversation = await display_conversation(api_key, conversation_id)
            
            # Return the formatted conversation and update the UI
            yield formatted_conversation, gr.update(visible=True), conversation_id
        except Exception as e:
            error_message = f"Error updating conversation: {str(e)}"
            logging.error(error_message)
            yield error_message, gr.update(visible=False), None

    conversation_table.select(
        update_conversation,
        inputs=[api_key],
        outputs=[conversation_details, delete_button, selected_conversation_id],
        # _js="(api_key, evt) => [api_key, evt]",  # This ensures the evt object is passed correctly
    )
    # .then(
    #     lambda: None,  # This is a no-op function
    #     None,  # No inputs
    #     None,  # No outputs
    #     _js="""
    #     () => {
    #         // Scroll to the conversation details
    #         document.querySelector('#conversation_details').scrollIntoView({behavior: 'smooth'});
    #     }
    #     """
    # )

    delete_button.click(
        delete_selected_conversation,
        inputs=[api_key, selected_conversation_id],
        outputs=[conversation_details, conversation_table, info_text, delete_button, conversation_details]
    )

    async def change_page(api_key: str, direction: int) -> Tuple[pd.DataFrame, str, gr.update, gr.update]:
        global current_page, total_pages
        current_page += direction
        current_page = max(1, min(current_page, total_pages))  # Ensure page is within bounds
        df, info, current_page, total_pages = await list_conversations(api_key)
        prev_disabled = current_page == 1
        next_disabled = current_page == total_pages
        return df, info, gr.update(interactive=not prev_disabled), gr.update(interactive=not next_disabled)

    prev_page.click(partial(change_page, direction=-1), inputs=[api_key], outputs=[conversation_table, info_text, prev_page, next_page])
    next_page.click(partial(change_page, direction=1), inputs=[api_key], outputs=[conversation_table, info_text, prev_page, next_page])

    gr.Markdown("## Chat about the conversation")
    
    chat_interface = gr.ChatInterface(
        respond,
        additional_inputs=[
            gr.Textbox(value="You are a friendly Chatbot. Analyze and discuss the given conversation context.", label="System message"),
            gr.Slider(minimum=1, maximum=2048, value=512, step=1, label="Max new tokens"),
            gr.Slider(minimum=0.1, maximum=4.0, value=0.7, step=0.1, label="Temperature"),
            gr.Slider(minimum=0.1, maximum=1.0, value=0.95, step=0.05, label="Top-p (nucleus sampling)"),
            conversation_details
        ],
    )

if __name__ == "__main__":
    demo.launch()
