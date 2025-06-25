import streamlit as st
import asyncio
import os
import datetime as dt
from typing import TypedDict, Annotated, Sequence

# LangChain & LangGraph Imports
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
# --- IMPORT AIMessage ---
# We now need AIMessage to correctly build the conversation history
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq

# Import Google Calendar Tools from our other file
from google_calendar_tools import check_availability, book_appointment

# --- 1. Agent Definition (No changes here) ---

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]

tools = [check_availability, book_appointment]
tool_node = ToolNode(tools)

model = ChatGroq(
    temperature=0, 
    model_name="llama3-70b-8192",
    api_key=st.secrets.get("GROQ_API_KEY")
)
model = model.bind_tools(tools)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a helpful assistant that helps users book appointments in their Google Calendar.
Your primary tasks are to check for availability and book appointments.

Conversation Flow:
1. Greet the user and understand their request. The request might be vague (e.g., "tomorrow afternoon").
2. Clarify any ambiguities. You must determine a specific date and a time range to check for availability. For "afternoon", assume 12 PM to 5 PM. For "morning", 9 AM to 12 PM. For "evening", 5 PM to 8 PM.
3. Use the `check_availability` tool to find open slots. You MUST provide both a start and end time in ISO 8601 format to this tool.
4. Present the available slots to the user in a clear, friendly way.
5. Once the user confirms a time slot, ask for a title/summary for the meeting.
6. With all details confirmed (start time, end time, summary), use the `book_appointment` tool to create the event in the calendar.
7. Finally, confirm the booking with the user and provide the event details.

Important Rules:
- Do not assume the current date. Ask the user for it if they don't provide it. Today's date is {current_date}.
- Always confirm with the user before calling the `book_appointment` tool.
- If no slots are available, inform the user and ask if they'd like to try a different day or time.
- Your final response after a successful booking should be a confirmation message, not a tool call.
""",
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
).partial(current_date=str(dt.date.today()))

agent_runnable = prompt | model

def run_agent(state: AgentState):
    return {"messages": [agent_runnable.invoke(state)]}

def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "action"
    return "end"

workflow = StateGraph(AgentState)
workflow.add_node("agent", run_agent)
workflow.add_node("action", tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue, {"action": "action", "end": END})
workflow.add_edge("action", "agent")
agent_app = workflow.compile()


# --- 2. Streamlit Secrets and File Creation (No changes here) ---

def setup_google_credentials():
    if os.path.exists("credentials.json") and os.path.exists("token.json"):
        return
    try:
        creds_json_str = st.secrets["gcp_service_account"]["credentials"]
        token_json_str = st.secrets["gcp_service_account"]["token"]
        with open("credentials.json", "w") as f:
            f.write(creds_json_str)
        with open("token.json", "w") as f:
            f.write(token_json_str)
    except (KeyError, FileNotFoundError):
        st.error("Google credentials or token not found. Please configure them for deployment.")
        st.stop()
setup_google_credentials()


# --- 3. Streamlit UI and Logic (Changes are here!) ---

st.set_page_config(page_title="📅 AI Appointment Booker", page_icon="🤖", layout="centered")
st.title("🤖 AI Appointment Booker")
st.markdown("I can help you book appointments on your Google Calendar. Try asking: *'Do you have any availability tomorrow afternoon?'*")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! How can I help you schedule an appointment today?"}]

if "thread_id" not in st.session_state:
    st.session_state.thread_id = st.runtime.scriptrunner.get_script_run_ctx().session_id

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What would you like to do?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            
            # --- THE FIX: CONSTRUCT FULL HISTORY ---
            # Convert our session state message list into a list of LangChain message objects
            history = []
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    history.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    # Important: We need to use AIMessage for the assistant's replies
                    history.append(AIMessage(content=msg["content"]))

            # Pass the entire conversation history to the agent
            inputs = {"messages": history}
            # --- END OF FIX ---
            
            async def get_response():
                final_state = None
                async for event in agent_app.astream(inputs, config=config):
                    final_state = event
                return final_state['agent']['messages'][-1].content

            try:
                response_text = asyncio.run(get_response())
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            except Exception as e:
                error_message = f"An unexpected error occurred: {e}"
                st.error(error_message) # Corrected variable name from 'error__message' to 'error_message'
                st.session_state.messages.append({"role": "assistant", "content": error_message})