"""Cadence AI Streamlit UI Application - Clean & Focused Design.

This module provides a streamlined Streamlit-based web interface for the
Cadence AI multi-agent framework with focus on chat functionality.
"""

import os
from typing import Any, Dict

import streamlit as st

from cadence.ui.client import CadenceApiClient, ChatResult, PluginInfo, SystemStatus


def get_api_base_url() -> str:
    """Get API base URL from environment variables."""
    return os.environ.get("CADENCE_API_BASE_URL", "http://localhost:8000")


def get_default_user_config() -> Dict[str, str]:
    """Get default user configuration from environment variables."""
    return {
        "user_id": os.environ.get("CADENCE_DEFAULT_USER_ID", "anonymous"),
        "org_id": os.environ.get("CADENCE_DEFAULT_ORG_ID", "public"),
    }


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    defaults = {
        "messages": [],
        "thread_id": None,
        "conversation_id": None,
        "client": None,
        "selected_tone": "natural",
        "show_settings": False,
        "connection_status": "disconnected",
        "plugins": [],
        "system_status": None,
    }

    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def create_client(api_url: str) -> CadenceApiClient:
    """Create API client instance with connection status tracking."""
    try:
        client = CadenceApiClient(api_url)
        st.session_state.connection_status = "connected"
        return client
    except Exception:
        st.session_state.connection_status = "error"
        return None


def send_chat_message(client: CadenceApiClient, message: str, user_id: str, org_id: str, tone: str) -> ChatResult:
    """Send chat message and return response with error handling."""
    try:
        result = client.chat(
            message=message, thread_id=st.session_state.thread_id, user_id=user_id, org_id=org_id, tone=tone
        )
        return result
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        st.session_state.connection_status = "error"
        return None


def load_plugins(client: CadenceApiClient) -> list[PluginInfo]:
    """Load available plugins from API."""
    try:
        return client.get_plugins()
    except Exception as e:
        st.error(f"Error loading plugins: {str(e)}")
        return []


def load_system_status(client: CadenceApiClient) -> SystemStatus:
    """Load system status from API."""
    try:
        return client.get_system_status()
    except Exception as e:
        st.error(f"Error loading system status: {str(e)}")
        return None


def reload_plugins(client: CadenceApiClient) -> Dict[str, Any]:
    """Reload all plugins."""
    try:
        return client.reload_plugins()
    except Exception as e:
        st.error(f"Error reloading plugins: {str(e)}")
        return {}


def new_chat():
    """Start new chat session."""
    st.session_state.messages = []
    st.session_state.thread_id = None
    st.session_state.conversation_id = None


def render_message(message: dict):
    """Render chat message with proper styling."""
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.markdown(f"🤖 {message['content']}")
        else:
            st.markdown(message["content"])


def render_connection_status():
    """Render connection status indicator."""
    status_colors = {"connected": "🟢", "disconnected": "🟡", "error": "🔴"}

    status_text = {"connected": "Connected", "disconnected": "Connecting...", "error": "Connection Error"}

    status = st.session_state.connection_status
    return f"{status_colors.get(status, '⚪')} {status_text.get(status, 'Unknown')}"


def render_tone_selector():
    """Render tone selector with clean styling."""
    tone_options = {
        "natural": "💬 Natural",
        "explanatory": "📚 Explanatory",
        "formal": "🎩 Formal",
        "concise": "⚡ Concise",
        "learning": "🎓 Learning",
    }

    selected_tone = st.selectbox(
        "Style",
        options=list(tone_options.keys()),
        index=list(tone_options.keys()).index(st.session_state.selected_tone),
        format_func=lambda x: tone_options[x],
        key="tone_selector",
        help="Response style",
    )

    st.session_state.selected_tone = selected_tone
    return selected_tone


def main():
    """Main Streamlit application entry point."""
    st.set_page_config(page_title="Cadence AI", page_icon="🤖", layout="centered", initial_sidebar_state="expanded")

    # Custom CSS for cleaner appearance
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
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Initialize session state
    initialize_session_state()

    # Sidebar for plugin management
    with st.sidebar:
        st.header("🔌 Plugin Management")

        # Create client for sidebar operations
        api_url = get_api_base_url()
        if st.session_state.client is None:
            st.session_state.client = create_client(api_url)

        # Plugin refresh button
        if st.button("🔄 Refresh Plugins", use_container_width=True):
            with st.spinner("Refreshing plugins..."):
                result = reload_plugins(st.session_state.client)
                if result:
                    st.success("Plugins reloaded!")
                    st.session_state.plugins = load_plugins(st.session_state.client)
                else:
                    st.error("Failed to reload plugins")

        # Load plugins on first load
        if not st.session_state.plugins and st.session_state.client:
            with st.spinner("Loading plugins..."):
                st.session_state.plugins = load_plugins(st.session_state.client)

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
    st.title("🤖 Cadence AI")
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
            st.markdown(f"**Status:** {render_connection_status()}")
        with col2:
            st.markdown(
                f"**Session:** {st.session_state.thread_id[:8]}..."
                if st.session_state.thread_id
                else "**Session:** New"
            )

        # Second row: Style
        selected_tone = render_tone_selector()

    # New chat button right after settings
    if st.button("New Chat", help="Start a fresh conversation", use_container_width=True):
        new_chat()
        st.rerun()

    # Main chat interface - using default Streamlit chat
    if prompt := st.chat_input("💭 Ask me anything...", key="main_chat_input"):
        if not st.session_state.client:
            st.error("⚠️ Please check your connection in Settings first.")
            st.stop()

        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get AI response
        with st.spinner("🤔 Thinking..."):
            result = send_chat_message(st.session_state.client, prompt, user_id, org_id, selected_tone)

            if result:
                # Update session tracking
                if result.thread_id:
                    st.session_state.thread_id = result.thread_id
                if result.conversation_id:
                    st.session_state.conversation_id = result.conversation_id

                # Add AI response
                st.session_state.messages.append(
                    {"role": "assistant", "content": result.response, "metadata": result.metadata}
                )

                # Rerun to show the new message
                st.rerun()
            else:
                st.error("❌ Failed to get response. Please check your connection.")

    # Display chat messages with response data
    if st.session_state.messages:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    # Show AI response
                    st.markdown(f"🤖 {message['content']}")

                    # Show response data if available
                    if "metadata" in message and message["metadata"]:
                        with st.expander("📊 Response Data", expanded=False):
                            # Token usage
                            if "token_usage" in message["metadata"]:
                                token_data = message["metadata"]["token_usage"]
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Input Tokens", token_data.get("input_tokens", 0))
                                with col2:
                                    st.metric("Output Tokens", token_data.get("output_tokens", 0))
                                with col3:
                                    st.metric("Total Tokens", token_data.get("total_tokens", 0))

                            # Agent information
                            if "agent_hops" in message["metadata"]:
                                hops = message["metadata"]["agent_hops"]
                                if hops is not None:
                                    st.write(f"**Agent Hops:** {hops}")

                            if "tools_used" in message["metadata"] and message["metadata"]["tools_used"]:
                                tools = message["metadata"]["tools_used"]
                                if tools:
                                    st.write(f"**Tools Used:** {', '.join(tools)}")

                            # Processing time
                            if "processing_time" in message["metadata"]:
                                proc_time = message["metadata"]["processing_time"]
                                if proc_time is not None:
                                    try:
                                        formatted_time = f"{float(proc_time):.2f}s"
                                        st.write(f"**Processing Time:** {formatted_time}")
                                    except (ValueError, TypeError):
                                        st.write(f"**Processing Time:** {proc_time}")

                            # Model information
                            if "model_used" in message["metadata"]:
                                model = message["metadata"]["model_used"]
                                if model:
                                    st.write(f"**Model:** {model}")

                            # Raw metadata
                            st.write("**Raw Metadata:**")
                            st.json(message["metadata"])
                else:
                    st.markdown(message["content"])
    else:
        # Welcome message for new users
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

    # Footer
    st.markdown("---")
    st.markdown(
        '<div style="text-align: center; color: #888; padding: 1rem;">Powered by Cadence AI Framework</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
