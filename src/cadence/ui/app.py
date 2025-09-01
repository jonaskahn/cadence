"""Cadence AI Streamlit UI Application - Clean & Focused Design.

This module provides a streamlined Streamlit-based web interface for the
Cadence AI multi-agent framework with focus on chat functionality.
"""

import os
import time
from typing import Any, Dict

import streamlit as st

from cadence.ui.client import CadenceApiClient, ChatResult, PluginInfo, SystemStatus


def get_api_base_url() -> str:
    """Get API base URL from environment variables with localhost fallback."""
    return os.environ.get("CADENCE_API_BASE_URL", "http://localhost:8000")


def get_default_user_config() -> Dict[str, str]:
    """Get default user configuration from environment variables with fallback values."""
    return {
        "user_id": os.environ.get("CADENCE_DEFAULT_USER_ID", "anonymous"),
        "org_id": os.environ.get("CADENCE_DEFAULT_ORG_ID", "public"),
    }


def initialize_session_state():
    """Initialize Streamlit session state with default values for chat interface."""
    default_session_values = {
        "messages": [],
        "thread_id": None,
        "conversation_id": None,
        "client": None,
        "selected_tone": "natural",
        "show_settings": False,
        "connection_status": "disconnected",
        "plugins": [],
        "system_status": None,
        "is_processing": False,
    }

    for session_key, default_value in default_session_values.items():
        if session_key not in st.session_state:
            st.session_state[session_key] = default_value


def create_api_client(api_base_url: str) -> CadenceApiClient:
    """Create API client instance and update connection status."""
    try:
        api_client = CadenceApiClient(api_base_url)
        st.session_state.connection_status = "connected"
        return api_client
    except Exception:
        st.session_state.connection_status = "error"
        return None


def send_chat_message(
    api_client: CadenceApiClient, user_message: str, user_id: str, org_id: str, response_tone: str
) -> ChatResult:
    """Send chat message to API and return response with error handling."""
    try:
        chat_result = api_client.chat(
            user_message=user_message,
            thread_id=st.session_state.thread_id,
            user_id=user_id,
            org_id=org_id,
            tone=response_tone,
        )
        return chat_result
    except Exception as error:
        st.error(f"Connection error: {str(error)}")
        st.session_state.connection_status = "error"
        return None


def load_available_plugins(api_client: CadenceApiClient) -> list[PluginInfo]:
    """Load available plugins from API with error handling."""
    try:
        return api_client.get_plugins()
    except Exception as error:
        st.error(f"Error loading plugins: {str(error)}")
        return []


def load_system_status(api_client: CadenceApiClient) -> SystemStatus:
    """Load system status from API with error handling."""
    try:
        return api_client.get_system_status()
    except Exception as error:
        st.error(f"Error loading system status: {str(error)}")
        return None


def reload_all_plugins(api_client: CadenceApiClient) -> Dict[str, Any]:
    """Reload all plugins and return result with error handling."""
    try:
        return api_client.reload_plugins()
    except Exception as error:
        st.error(f"Error reloading plugins: {str(error)}")
        return {}


def start_new_chat_session():
    """Reset session state to start a new chat conversation."""
    st.session_state.messages = []
    st.session_state.thread_id = None
    st.session_state.conversation_id = None
    st.session_state.is_processing = False


def render_chat_message(chat_message: dict):
    """Render individual chat message with role-based styling."""
    with st.chat_message(chat_message["role"]):
        if chat_message["role"] == "assistant":
            st.markdown(f"🤖 {chat_message['content']}")
        else:
            st.markdown(chat_message["content"])


def get_connection_status_display():
    """Get formatted connection status with emoji and text."""
    status_emoji_map = {"connected": "🟢", "disconnected": "🟡", "error": "🔴"}
    status_text_map = {"connected": "Connected", "disconnected": "Connecting...", "error": "Connection Error"}

    current_status = st.session_state.connection_status
    return f"{status_emoji_map.get(current_status, '⚪')} {status_text_map.get(current_status, 'Unknown')}"


def render_response_tone_selector():
    """Render response tone selector with emoji labels."""
    tone_display_options = {
        "natural": "💬 Natural",
        "explanatory": "📚 Explanatory",
        "formal": "🎩 Formal",
        "concise": "⚡ Concise",
        "learning": "🎓 Learning",
    }

    current_tone = st.session_state.selected_tone
    tone_options_list = list(tone_display_options.keys())

    selected_tone = st.selectbox(
        "Style",
        options=tone_options_list,
        index=tone_options_list.index(current_tone),
        format_func=lambda tone_key: tone_display_options[tone_key],
        key="tone_selector",
        help="Response style",
    )

    st.session_state.selected_tone = selected_tone
    return selected_tone


def get_ai_thinking_message():
    """Get animated AI thinking message that cycles over time."""
    thinking_messages = [
        "🤔 AI is thinking...",
        "💭 Processing your request...",
        "⚡ Generating response...",
        "🔄 Working on it...",
    ]

    current_time_index = int(time.time()) % len(thinking_messages)
    return thinking_messages[current_time_index]


def display_chat_messages():
    """Display all chat messages with metadata and thinking indicator."""
    for chat_message in st.session_state.messages:
        with st.chat_message(chat_message["role"]):
            if chat_message["role"] == "assistant":
                st.markdown(f"**AI Assistant**")
                st.markdown(chat_message["content"])

                if "metadata" in chat_message and chat_message["metadata"]:
                    metrics_tab, tools_tab, details_tab = st.tabs(["📊 Metrics", "🔧 Tools", "📋 Details"])

                    with metrics_tab:
                        if "token_usage" in chat_message["metadata"]:
                            token_usage_data = chat_message["metadata"]["token_usage"]
                            input_col, output_col, total_col = st.columns(3)
                            with input_col:
                                st.metric("📥 Input", token_usage_data.get("input_tokens", 0))
                            with output_col:
                                st.metric("📤 Output", token_usage_data.get("output_tokens", 0))
                            with total_col:
                                st.metric("📊 Total", token_usage_data.get("total_tokens", 0))

                        if "processing_time" in chat_message["metadata"]:
                            processing_time = chat_message["metadata"]["processing_time"]
                            if processing_time is not None:
                                try:
                                    formatted_processing_time = f"{float(processing_time):.2f}s"
                                    st.metric("⏱️ Speed", formatted_processing_time)
                                except (ValueError, TypeError):
                                    st.metric("⏱️ Speed", str(processing_time))

                    with tools_tab:
                        if "agent_hops" in chat_message["metadata"]:
                            agent_hops_count = chat_message["metadata"]["agent_hops"]
                            if agent_hops_count is not None:
                                st.info(f"🔄 **Agent Hops:** {agent_hops_count}")

                        if "tools_used" in chat_message["metadata"] and chat_message["metadata"]["tools_used"]:
                            used_tools = chat_message["metadata"]["tools_used"]
                            if used_tools:
                                st.success(f"🛠️ **Tools Used:** {', '.join(used_tools)}")

                        if "multi_agent" in chat_message["metadata"]:
                            if chat_message["metadata"]["multi_agent"]:
                                st.warning("🤖 **Multi-Agent Response**")

                    with details_tab:
                        if "model_used" in chat_message["metadata"]:
                            model_name = chat_message["metadata"]["model_used"]
                            if model_name:
                                st.info(f"🧠 **Model:** {model_name}")

                        if "thread_message_count" in chat_message["metadata"]:
                            message_count = chat_message["metadata"]["thread_message_count"]
                            st.info(f"💬 **Message #{message_count}** in this thread")

                        with st.expander("🔍 Raw Metadata", expanded=False):
                            st.json(chat_message["metadata"])
            else:
                st.markdown(f"👤 **You**")
                st.markdown(chat_message["content"])

                if "timestamp" in chat_message:
                    st.caption(f"📅 {chat_message['timestamp']}")

    if st.session_state.is_processing:
        with st.chat_message("assistant"):
            st.markdown(f"**AI Assistant**")
            st.markdown(get_ai_thinking_message())


def process_user_message(user_prompt: str, user_id: str, org_id: str, response_tone: str):
    """Process user message and trigger AI response generation."""
    if not st.session_state.client:
        st.error("⚠️ Please check your connection in Settings first.")
        return

    st.session_state.messages.append({"role": "user", "content": user_prompt})
    st.session_state.is_processing = True
    st.rerun()


def get_ai_response(user_prompt: str, user_id: str, org_id: str, response_tone: str):
    """Get AI response and update session state with result."""
    try:
        chat_result = send_chat_message(st.session_state.client, user_prompt, user_id, org_id, response_tone)

        if chat_result:
            if chat_result.thread_id:
                st.session_state.thread_id = chat_result.thread_id
            if chat_result.conversation_id:
                st.session_state.conversation_id = chat_result.conversation_id

            st.session_state.messages.append(
                {"role": "assistant", "content": chat_result.response, "metadata": chat_result.metadata}
            )
        else:
            st.error("❌ Failed to get response. Please check your connection.")

    except Exception as error:
        st.error(f"❌ Error: {str(error)}")
    finally:
        st.session_state.is_processing = False


def main():
    """Main Streamlit application entry point."""
    st.set_page_config(page_title="Cadence AI", page_icon="🤖", layout="centered", initial_sidebar_state="expanded")

    # Enhanced CSS for better chat experience
    st.markdown(
        """
    <style>
        .main-header {
            text-align: center;
            padding: 1rem 0;
            margin-bottom: 1rem;
        }
        .stSelectbox > div > div {
            background-color: #f8f9fa;
        }
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 100%;
        }
        .stExpander {
            margin-bottom: 1rem;
        }
        
        /* Enhanced chat styling */
        .stChatMessage {
            border-radius: 15px;
            margin: 10px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .stChatMessage[data-testid="chat_message_user"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .stChatMessage[data-testid="chat_message_assistant"] {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        
        /* Button enhancements */
        .stButton > button {
            border-radius: 20px;
            border: none;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }
        
        /* Progress bar styling */
        .stProgress > div > div > div {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        }
        
        /* Metric styling */
        .stMetric {
            background: rgba(255,255,255,0.1);
            padding: 10px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.2);
        }

        /* Hide streamlit loading spinner */
        .stSpinner {
            display: none !important;
        }
        
        /* Custom thinking indicator */
        .thinking-indicator {
            animation: pulse 1.5s ease-in-out infinite alternate;
        }
        
        @keyframes pulse {
            from { opacity: 0.6; }
            to { opacity: 1; }
        }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Initialize session state
    initialize_session_state()

    # Sidebar for plugin management
    with st.sidebar:
        # Chat controls at the top of sidebar
        st.header("💬 Chat Controls")

        if st.button("🆕 New Chat", use_container_width=True):
            start_new_chat_session()
            st.rerun()

        if st.session_state.thread_id:
            st.info(f"**Active Thread:** {st.session_state.thread_id[:8]}...")
        else:
            st.info("**New Conversation**")

        st.markdown("---")  # Separator

        st.header("🔌 Plugin Management")

        # Create client for sidebar operations
        api_url = get_api_base_url()
        if st.session_state.client is None:
            st.session_state.client = create_api_client(api_url)

        # Plugin refresh button
        if st.button("🔄 Refresh Plugins", use_container_width=True):
            with st.spinner("Refreshing plugins..."):
                reload_result = reload_all_plugins(st.session_state.client)
                if reload_result:
                    st.success("Plugins reloaded!")
                    st.session_state.plugins = load_available_plugins(st.session_state.client)
                else:
                    st.error("Failed to reload plugins")

        # Load plugins on first load
        if not st.session_state.plugins and st.session_state.client:
            with st.spinner("Loading plugins..."):
                st.session_state.plugins = load_available_plugins(st.session_state.client)

        # Display plugins
        if st.session_state.plugins:
            st.subheader("Available Plugins")
            for plugin in st.session_state.plugins:
                status_color = "🟢" if plugin.status == "healthy" else "🔴"
                with st.expander(f"{status_color} {plugin.name}"):
                    st.write(f"**Status:** {plugin.status}")
                    st.write(f"**Version:** {plugin.version}")
                    st.write(f"**Description:** {plugin.description}")
                    if plugin.capabilities:
                        st.write(f"**Capabilities:** {', '.join(plugin.capabilities)}")
        else:
            st.info("No plugins available")

        # System status section
        st.header("📊 System Status")
        if st.button("🔄 Refresh Status", use_container_width=True):
            with st.spinner("Loading status..."):
                st.session_state.system_status = load_system_status(st.session_state.client)

        if not st.session_state.system_status and st.session_state.client:
            st.session_state.system_status = load_system_status(st.session_state.client)

        if st.session_state.system_status:
            status_icon = "🟢" if st.session_state.system_status.status == "operational" else "🔴"
            st.metric("System", f"{status_icon} {st.session_state.system_status.status}")
            st.metric("Total Sessions", st.session_state.system_status.total_sessions)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Healthy", len(st.session_state.system_status.healthy_plugins))
            with col2:
                st.metric("Failed", len(st.session_state.system_status.failed_plugins))

    # Header
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title("🫆 Cadence AI")
    st.markdown("*Intelligent conversations powered by multi-agent AI*")
    st.markdown("</div>", unsafe_allow_html=True)

    # Get user config for API calls
    user_config = get_default_user_config()
    user_id = user_config["user_id"]
    org_id = user_config["org_id"]

    # Settings in expander
    with st.expander("⚙️ Settings"):
        # First row: Status and Session
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Status:** {get_connection_status_display()}")
        with col2:
            st.markdown(
                f"**Session:** {st.session_state.thread_id[:8]}..."
                if st.session_state.thread_id
                else "**Session:** New"
            )

        # Second row: Style
        selected_tone = render_response_tone_selector()

    # Display all messages (including thinking indicator)
    display_chat_messages()

    # Handle AI response generation if we're processing
    if st.session_state.is_processing and len(st.session_state.messages) > 0:
        # Get the last user message
        last_message = st.session_state.messages[-1]
        if last_message["role"] == "user":
            get_ai_response(last_message["content"], user_id, org_id, selected_tone)
            st.rerun()  # Rerun to show the AI response

    # Chat input
    if prompt := st.chat_input("💭 Ask me anything...", key="main_chat_input", disabled=st.session_state.is_processing):
        process_user_message(prompt, user_id, org_id, selected_tone)

    # Show welcome message if no messages
    if not st.session_state.messages:
        # Enhanced welcome message with interactive elements
        st.markdown(
            """
        <div style="text-align: center; padding: 3rem 0; color: #666;">
            <h3>👋 Welcome to Cadence AI!</h3>
            <p>Start a conversation by typing a message below.</p>
            <p><em>Choose your preferred response style in Settings and start chatting.</em></p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Quick start suggestions
        st.markdown("### 💡 **Quick Start Suggestions**")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🤖 Ask about capabilities", use_container_width=True):
                process_user_message("What can you help me with?", user_id, org_id, selected_tone)

            if st.button("🔍 Search for information", use_container_width=True):
                process_user_message("Can you help me search for information?", user_id, org_id, selected_tone)

        with col2:
            if st.button("📚 Explain a concept", use_container_width=True):
                process_user_message("Can you explain how AI works in simple terms?", user_id, org_id, selected_tone)

            if st.button("🧮 Math help", use_container_width=True):
                process_user_message("Can you help me with a math problem?", user_id, org_id, selected_tone)

    # Footer
    st.markdown("---")
    st.markdown(
        '<div style="text-align: center; color: #888; padding: 1rem;">Powered by Cadence AI Framework</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
