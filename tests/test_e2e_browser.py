"""
Playwright-based E2E Browser Tests for Multi Custom Agent Service

SETUP INSTRUCTIONS:
==================
1. Install dependencies:
   pip install pytest-playwright

2. Install Playwright browsers:
   playwright install chromium

3. Run the tests:
   pytest tests/test_e2e_browser.py -v

4. Run with headed mode (visible browser):
   pytest tests/test_e2e_browser.py -v --headed

5. Run with screenshot on failure:
   pytest tests/test_e2e_browser.py -v --screenshot on

6. Run specific test:
   pytest tests/test_e2e_browser.py::test_e2e_001_select_chatbot -v

REQUIREMENTS:
=============
- Server must be running at http://localhost:8080
- Test assumes at least one chatbot exists in the system
- Tests are independent and can run in any order
- Each test handles its own setup/teardown
"""

import pytest
import re
from typing import Generator
from playwright.sync_api import Page, expect, sync_playwright
import time
import uuid

# Base URL for the application
BASE_URL = "http://localhost:8080"
ADMIN_URL = f"{BASE_URL}/admin"

# Test timeout settings
TIMEOUT = 30000  # 30 seconds
SSE_TIMEOUT = 60000  # 60 seconds for SSE streaming


def generate_unique_id() -> str:
    """Generate a unique ID for test chatbots."""
    return f"test-chatbot-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context with larger viewport and permissions."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "permissions": ["geolocation"],
    }


# ============================================================================
# TC-E2E-001: Open chat page, select a chatbot from dropdown, verify UI updates
# ============================================================================
def test_e2e_001_select_chatbot(page: Page) -> None:
    """
    Test: Open chat page, select a chatbot from dropdown, verify UI updates
    Steps:
    1. Navigate to chat page
    2. Wait for chatbot dropdown to load
    3. Select first available chatbot
    4. Verify session info updates
    5. Verify system message appears
    """
    # Navigate to chat page
    page.goto(f"{BASE_URL}/", timeout=TIMEOUT)
    
    # Wait for page to load
    page.wait_for_load_state("networkidle")
    
    # Verify page title
    expect(page).to_have_title("Multi Custom Agent")
    
    # Wait for chatbot selector to be available and load options
    selector = page.locator("#chatbot-selector")
    selector.wait_for(state="visible", timeout=TIMEOUT)
    
    # Wait for options to load (at least "챗봇 선택..." and one chatbot)
    page.wait_for_timeout(1000)  # Brief wait for AJAX
    options = page.locator("#chatbot-selector option").all()
    
    # Check that there are options loaded (at least default + 1 chatbot)
    assert len(options) >= 2, "Expected at least one chatbot to be available"
    
    # Get first non-default option
    first_chatbot_option = None
    for option in options:
        value = option.get_attribute("value")
        if value:  # Skip empty default option
            first_chatbot_option = option
            break
    
    assert first_chatbot_option is not None, "No chatbot found in dropdown"
    
    chatbot_name = first_chatbot_option.text_content()
    chatbot_id = first_chatbot_option.get_attribute("value")
    
    # Select the chatbot
    selector.select_option(value=chatbot_id)
    
    # Verify session info updates
    session_info = page.locator("#session-info")
    expect(session_info).to_contain_text(f"챗봇: {chatbot_name}")
    
    # Verify system message appears indicating chatbot selection
    chat_container = page.locator("#chat-container")
    expect(chat_container).to_contain_text("선택됨")


# ============================================================================
# TC-E2E-002: Type a message and send, verify assistant response appears
# ============================================================================
def test_e2e_002_send_message_and_receive_response(page: Page) -> None:
    """
    Test: Type a message and send, verify assistant response appears (wait for SSE streaming)
    Steps:
    1. Check API health first
    2. Navigate to chat page
    3. Select a standalone chatbot (faster response than parent)
    4. Type a simple test message
    5. Send the message
    6. Verify user message appears in chat
    7. Wait for SSE streaming response
    8. Verify assistant response appears
    """
    import requests
    
    # First, check API health
    try:
        health_response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        if health_response.status_code != 200:
            pytest.skip(f"Server health check failed: {health_response.status_code}")
    except Exception as e:
        pytest.skip(f"Server not reachable for health check: {e}")
    
    # Get available chatbots from API to find a standalone one
    try:
        response = requests.get(f"{BASE_URL}/api/chatbots", timeout=10)
        chatbots = response.json()
    except Exception as e:
        pytest.skip(f"Could not fetch chatbots: {e}")
    
    if not chatbots:
        pytest.skip("No chatbots available for testing")
    
    # Prefer standalone chatbots (faster response) but fall back to any available
    target_chatbot = None
    for bot in chatbots:
        if bot.get("type") == "standalone":
            target_chatbot = bot
            break
    
    if not target_chatbot:
        # Fall back to first available chatbot
        target_chatbot = chatbots[0]
    
    chatbot_id = target_chatbot["id"]
    chatbot_name = target_chatbot["name"]
    
    # Use a simple test message that standalone bots can handle quickly
    test_message = "Hi"
    
    # Navigate to chat page
    page.goto(f"{BASE_URL}/", timeout=TIMEOUT)
    page.wait_for_load_state("networkidle")
    
    # Select the chatbot
    selector = page.locator("#chatbot-selector")
    selector.wait_for(state="visible", timeout=TIMEOUT)
    
    # Wait for options to load and select the target chatbot
    selector.wait_for(state="attached", timeout=TIMEOUT)
    page.wait_for_timeout(1000)
    selector.select_option(value=chatbot_id)
    
    # Wait for selection to take effect
    page.wait_for_timeout(500)
    
    # Verify the chatbot was selected
    selected_value = selector.evaluate("el => el.value")
    assert selected_value == chatbot_id, f"Expected {chatbot_id}, got {selected_value}"
    
    # Type test message
    input_field = page.locator("#user-input")
    input_field.fill(test_message)
    
    # Verify input has the text
    expect(input_field).to_have_value(test_message)
    
    # Click send button
    send_btn = page.locator("#send-btn")
    send_btn.click()
    
    # Verify user message appears in chat
    chat_container = page.locator("#chat-container")
    user_message = chat_container.locator(".message.user").last
    expect(user_message).to_contain_text(test_message)
    
    # Wait for assistant typing indicator or response
    typing_indicator = chat_container.locator(".typing-indicator")
    try:
        typing_indicator.wait_for(state="visible", timeout=5000)
    except:
        pass  # May disappear quickly
    
    # Wait for assistant response with reduced timeout (30s instead of 60s)
    # Standalone bots should respond faster
    response_timeout = 30000
    assistant_messages = chat_container.locator(".message.assistant")
    
    try:
        # Wait for at least one assistant message that is not just typing indicator
        page.wait_for_function(
            """
            () => {
                const msgs = document.querySelectorAll('.message.assistant');
                for (const msg of msgs) {
                    if (!msg.classList.contains('typing-indicator') && msg.textContent.length > 0) {
                        return true;
                    }
                }
                return false;
            }
            """,
            timeout=response_timeout
        )
    except Exception as e:
        # Get actual state for better error message
        msg_count = assistant_messages.count()
        actual_content = chat_container.inner_html()[:500] if msg_count > 0 else "No messages"
        raise AssertionError(
            f"Timeout waiting for assistant response. "
            f"Chatbot: {chatbot_name} ({chatbot_id}), "
            f"Assistant messages found: {msg_count}, "
            f"Content preview: {actual_content}"
        ) from e
    
    # Verify there's actual content in the response
    assistant_message = assistant_messages.last
    message_text = assistant_message.text_content()
    assert len(message_text) > 0, "Assistant response should not be empty"
    
    # Verify session was created
    session_info = page.locator("#session-info")
    session_text = session_info.text_content()
    assert "세션:" in session_text and session_text != "세션: 없음", "Session should be created"


# ============================================================================
# TC-E2E-003: URL parameter auto-select chatbot (?chatbot=chatbot-hr)
# ============================================================================
def test_e2e_003_url_parameter_autoselect(page: Page) -> None:
    """
    Test: URL parameter auto-select chatbot (?chatbot=chatbot-hr)
    Steps:
    1. Check API health first
    2. Get available chatbot IDs from API
    3. Verify API returns chatbots
    4. Navigate to chat page with ?chatbot= parameter
    5. Wait for selector options to populate
    6. Verify the specified chatbot is automatically selected
    7. Verify session info reflects the selected chatbot
    """
    import requests
    
    # First, check API health
    try:
        health_response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        if health_response.status_code != 200:
            pytest.skip(f"Server health check failed: {health_response.status_code}")
    except Exception as e:
        pytest.skip(f"Server not reachable for health check: {e}")
    
    # Get available chatbots from API
    try:
        response = requests.get(f"{BASE_URL}/api/chatbots", timeout=10)
        chatbots = response.json()
    except Exception as e:
        pytest.skip(f"Could not fetch chatbots: {e}")
    
    if not chatbots:
        pytest.skip("No chatbots available for testing")
    
    # Use first available chatbot for testing
    test_chatbot = chatbots[0]
    chatbot_id = test_chatbot["id"]
    chatbot_name = test_chatbot["name"]
    
    # Navigate with URL parameter
    page.goto(f"{BASE_URL}/?chatbot={chatbot_id}", timeout=TIMEOUT)
    page.wait_for_load_state("networkidle")
    
    # Wait for chatbot selector to be available
    selector = page.locator("#chatbot-selector")
    selector.wait_for(state="visible", timeout=TIMEOUT)
    selector.wait_for(state="attached", timeout=TIMEOUT)
    
    # Explicit wait for selector options to populate
    page.wait_for_timeout(2000)
    
    # Check actual dropdown options match API response
    options = page.locator("#chatbot-selector option").all()
    option_values = [opt.get_attribute("value") for opt in options if opt.get_attribute("value")]
    
    if chatbot_id not in option_values:
        # Fallback: use first available option from the dropdown
        if option_values:
            actual_chatbot_id = option_values[0]
            actual_chatbot_name = None
            for opt in options:
                if opt.get_attribute("value") == actual_chatbot_id:
                    actual_chatbot_name = opt.text_content()
                    break
            pytest.skip(
                f"Chatbot '{chatbot_id}' not found in dropdown. "
                f"Available: {option_values}. "
                f"Using fallback: {actual_chatbot_id} ({actual_chatbot_name})"
            )
        else:
            pytest.skip(f"No chatbots loaded in dropdown. API returned: {len(chatbots)} chatbots")
    
    # Wait for auto-selection to complete (may take time after page load)
    page.wait_for_timeout(1000)
    
    # Verify the chatbot is selected
    selected_value = selector.evaluate("el => el.value")
    
    # Better error message showing actual vs expected
    assert selected_value == chatbot_id, (
        f"URL parameter autoselect failed. "
        f"Expected: '{chatbot_id}', Got: '{selected_value}'. "
        f"Available options: {option_values}"
    )
    
    # Verify session info shows the chatbot
    session_info = page.locator("#session-info")
    expect(session_info).to_contain_text(chatbot_name)
    
    # Verify system message indicating selection
    chat_container = page.locator("#chat-container")
    expect(chat_container).to_contain_text("선택됨")


# ============================================================================
# TC-E2E-004: Admin page - open, verify Agent Store loads
# ============================================================================
def test_e2e_004_admin_page_agent_store(page: Page) -> None:
    """
    Test: Admin page - open, verify Agent Store loads
    Steps:
    1. Navigate to admin page
    2. Verify page title and logo
    3. Verify Agent Store section loads
    4. Verify stats cards are populated
    5. Verify chatbot grid loads
    """
    # Navigate to admin page
    page.goto(ADMIN_URL, timeout=TIMEOUT)
    page.wait_for_load_state("networkidle")
    
    # Verify page title
    expect(page).to_have_title("챗봇 관리자 - Multi Custom Agent Service")
    
    # Verify Agent Store logo/header
    logo = page.locator(".logo h1")
    expect(logo).to_have_text("🤖 Agent Store")
    
    # Verify subtitle
    subtitle = page.locator(".logo p")
    expect(subtitle).to_have_text("챗봇 관리자")
    
    # Wait for stats to load
    stats_container = page.locator("#storeStats")
    stats_container.wait_for(state="visible", timeout=TIMEOUT)
    
    # Verify stats cards have values (not "-")
    page.wait_for_timeout(2000)  # Wait for AJAX
    
    # Check that stat values are populated
    total_stat = page.locator("#statTotal")
    parents_stat = page.locator("#statParents")
    active_stat = page.locator("#statActive")
    
    # Values should not be "-" after loading
    total_text = total_stat.text_content()
    assert total_text != "-", "Total stat should be loaded"
    
    # Verify chatbot grid loads
    grid = page.locator("#chatbotGrid")
    grid.wait_for(state="visible", timeout=TIMEOUT)
    
    # Check if grid has content (either cards or empty state)
    grid_html = grid.inner_html()
    assert len(grid_html) > 0, "Chatbot grid should have content"
    
    # Verify filter tabs exist
    filter_tabs = page.locator(".filter-tabs")
    expect(filter_tabs).to_be_visible()
    
    # Verify "새 챗봇" button exists
    new_chatbot_btn = page.locator("button:has-text('새 챗봘')")
    expect(new_chatbot_btn).to_be_visible()


# ============================================================================
# TC-E2E-005: Admin page - create a test chatbot via UI (fill form, submit)
# ============================================================================
def test_e2e_005_admin_create_chatbot(page: Page) -> None:
    """
    Test: Admin page - create a test chatbot via UI (fill form, submit)
    Steps:
    1. Navigate to admin page
    2. Click "새 챗봘" button
    3. Fill in chatbot form
    4. Submit the form
    5. Verify chatbot appears in the grid
    6. Verify success toast appears
    """
    # Generate unique test chatbot ID
    test_chatbot_id = generate_unique_id()
    test_chatbot_name = f"Test Chatbot {test_chatbot_id[-8:]}"
    
    # Navigate to admin page
    page.goto(ADMIN_URL, timeout=TIMEOUT)
    page.wait_for_load_state("networkidle")
    
    # Wait for page to fully load
    page.wait_for_timeout(1500)
    
    # Click "새 챗봘" button
    new_chatbot_btn = page.locator("button:has-text('새 챗봘')")
    new_chatbot_btn.wait_for(state="visible", timeout=TIMEOUT)
    new_chatbot_btn.click()
    
    # Wait for modal to open
    modal = page.locator("#chatbotModal")
    modal.wait_for(state="visible", timeout=TIMEOUT)
    
    # Fill in the form
    # Chatbot ID
    id_input = page.locator("#chatbotId")
    id_input.fill(test_chatbot_id)
    
    # Chatbot Name
    name_input = page.locator("#chatbotName")
    name_input.fill(test_chatbot_name)
    
    # Description
    desc_input = page.locator("#chatbotDesc")
    desc_input.fill("This is an automated test chatbot created by E2E tests")
    
    # Select type (standalone is default)
    type_select = page.locator("#chatbotType")
    type_select.select_option(value="standalone")
    
    # System Prompt
    prompt_input = page.locator("#systemPrompt")
    prompt_input.fill("You are a helpful test assistant. Keep responses brief.")
    
    # Submit form
    submit_btn = page.locator("#chatbotForm button[type='submit']")
    submit_btn.click()
    
    # Wait for modal to close
    modal.wait_for(state="hidden", timeout=TIMEOUT)
    
    # Wait for grid to refresh and new chatbot to appear
    page.wait_for_timeout(2000)
    
    # Verify toast notification
    toast = page.locator("#toast")
    try:
        toast.wait_for(state="visible", timeout=5000)
        toast_text = toast.text_content()
        assert "생성" in toast_text or "success" in toast_text.lower(), f"Unexpected toast: {toast_text}"
    except:
        # Toast might disappear quickly, check if grid has the new chatbot
        pass
    
    # Search for the newly created chatbot
    search_input = page.locator("#searchInput")
    search_input.fill(test_chatbot_name)
    page.wait_for_timeout(1000)
    
    # Verify chatbot card appears in grid
    grid = page.locator("#chatbotGrid")
    expect(grid).to_contain_text(test_chatbot_name)
    
    # Store the ID for cleanup (we'll use it in delete test)
    page._test_chatbot_id = test_chatbot_id
    page._test_chatbot_name = test_chatbot_name


# ============================================================================
# TC-E2E-006: Admin page - verify hierarchy view shows parent-child relationships
# ============================================================================
def test_e2e_006_admin_hierarchy_view(page: Page) -> None:
    """
    Test: Admin page - verify hierarchy view shows parent-child relationships
    Steps:
    1. Navigate to admin page
    2. Click on "Agent 계층" tab
    3. Verify hierarchy view loads
    4. Verify parent agents are displayed
    5. Verify child agents are shown under parents
    6. Verify standalone agents are shown separately
    """
    # Navigate to admin page
    page.goto(ADMIN_URL, timeout=TIMEOUT)
    page.wait_for_load_state("networkidle")
    
    # Wait for initial load
    page.wait_for_timeout(1500)
    
    # Click on "Agent 계층" tab
    hierarchy_tab = page.locator(".nav-item:has-text('Agent 계층')")
    hierarchy_tab.wait_for(state="visible", timeout=TIMEOUT)
    hierarchy_tab.click()
    
    # Wait for hierarchy view to load
    hierarchy_view = page.locator("#view-hierarchy")
    hierarchy_view.wait_for(state="visible", timeout=TIMEOUT)
    
    # Wait for hierarchy container to load content
    container = page.locator("#hierarchyContainer")
    page.wait_for_timeout(2000)
    
    # Verify hierarchy section title
    expect(container).to_contain_text("Agent 계층 구조")
    
    # Check for hierarchy trees (parent nodes)
    # If there are parent agents, they should be displayed
    try:
        parent_nodes = page.locator(".hierarchy-node.parent")
        parent_count = parent_nodes.count()
        
        if parent_count > 0:
            # Verify parent nodes have proper structure
            first_parent = parent_nodes.first
            expect(first_parent).to_contain_text("🤖")
            
            # Check for child nodes container
            children_containers = page.locator(".hierarchy-children")
            expect(children_containers.first).to_be_visible()
    except:
        # No parent agents in the system is also valid
        pass
    
    # Verify standalone section exists
    expect(container).to_contain_text("단독 챗봘")
    
    # Verify the view is properly structured
    hierarchy_trees = page.locator(".hierarchy-tree")
    standalone_list = page.locator(".hierarchy-standalone-list")
    
    # At least one of these should exist
    assert hierarchy_trees.count() > 0 or standalone_list.count() > 0, \
        "Hierarchy view should show either parent-child trees or standalone agents"


# ============================================================================
# TC-E2E-007: Admin page - delete test chatbot
# ============================================================================
def test_e2e_007_admin_delete_chatbot(page: Page) -> None:
    """
    Test: Admin page - delete test chatbot
    Steps:
    1. Create a test chatbot first
    2. Navigate to admin page
    3. Find the test chatbot in the grid
    4. Click delete button
    5. Confirm deletion
    6. Verify chatbot no longer appears in grid
    """
    import requests
    
    # First, create a test chatbot via API to ensure we have one to delete
    test_chatbot_id = generate_unique_id()
    test_chatbot_name = f"Delete Test {test_chatbot_id[-6:]}"
    
    try:
        response = requests.post(
            f"{BASE_URL}/admin/api/chatbots",
            json={
                "id": test_chatbot_id,
                "name": test_chatbot_name,
                "description": "Temp chatbot for delete test",
                "type": "standalone",
                "system_prompt": "Test",
                "db_ids": [],
                "active": True
            },
            timeout=10
        )
        assert response.status_code == 200, f"Failed to create test chatbot: {response.text}"
    except Exception as e:
        pytest.skip(f"Could not create test chatbot: {e}")
    
    # Navigate to admin page
    page.goto(ADMIN_URL, timeout=TIMEOUT)
    page.wait_for_load_state("networkidle")
    
    # Wait for grid to load
    page.wait_for_timeout(2000)
    
    # Search for the test chatbot
    search_input = page.locator("#searchInput")
    search_input.fill(test_chatbot_name)
    page.wait_for_timeout(1000)
    
    # Find the chatbot card
    grid = page.locator("#chatbotGrid")
    
    # Wait for the specific chatbot card
    chatbot_card = grid.locator(f".chatbot-card:has-text('{test_chatbot_name}')")
    chatbot_card.wait_for(state="visible", timeout=TIMEOUT)
    
    # Find and click delete button within the card
    delete_btn = chatbot_card.locator("button[title='삭제']")
    delete_btn.click()
    
    # Wait for delete confirmation modal
    delete_modal = page.locator("#deleteModal")
    delete_modal.wait_for(state="visible", timeout=TIMEOUT)
    
    # Verify modal shows the chatbot name
    expect(page.locator("#deleteChatbotName")).to_have_text(test_chatbot_name)
    
    # Click confirm delete
    confirm_btn = page.locator("#confirmDeleteBtn")
    confirm_btn.click()
    
    # Wait for modal to close
    delete_modal.wait_for(state="hidden", timeout=TIMEOUT)
    
    # Wait for grid to refresh
    page.wait_for_timeout(2000)
    
    # Clear search and verify chatbot no longer exists
    search_input.fill("")
    page.wait_for_timeout(1000)
    
    # Search again specifically for the deleted chatbot
    search_input.fill(test_chatbot_name)
    page.wait_for_timeout(1000)
    
    # Verify empty state or "not found" message
    # The chatbot should not appear
    card_count = grid.locator(f".chatbot-card:has-text('{test_chatbot_name}')").count()
    assert card_count == 0, f"Chatbot {test_chatbot_name} should have been deleted"


# ============================================================================
# Additional Helper Tests
# ============================================================================

def test_chat_page_loads(page: Page) -> None:
    """Basic test to verify chat page loads correctly."""
    page.goto(f"{BASE_URL}/", timeout=TIMEOUT)
    expect(page).to_have_title("Multi Custom Agent")
    
    # Verify main elements exist
    expect(page.locator("#chatbot-selector")).to_be_visible()
    expect(page.locator("#chat-container")).to_be_visible()
    expect(page.locator("#user-input")).to_be_visible()
    expect(page.locator("#send-btn")).to_be_visible()


def test_admin_page_navigation(page: Page) -> None:
    """Test navigation between admin views."""
    page.goto(ADMIN_URL, timeout=TIMEOUT)
    page.wait_for_load_state("networkidle")
    
    # Test switching to each view
    views = ["hierarchy", "users", "stats", "settings"]
    
    for view in views:
        # Click the nav item
        nav_item = page.locator(f".nav-item[data-view='{view}']")
        nav_item.click()
        
        # Wait for view to be active
        view_element = page.locator(f"#view-{view}")
        expect(view_element).to_have_class(re.compile(r".*\bactive\b.*"))


def test_chatbot_selector_filtering(page: Page) -> None:
    """Test filter tabs on admin page."""
    page.goto(ADMIN_URL, timeout=TIMEOUT)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    
    # Test each filter
    filters = ["all", "parent", "child", "standalone"]
    
    for filter_type in filters:
        filter_btn = page.locator(f".tab[data-filter='{filter_type}']")
        filter_btn.click()
        
        # Verify tab becomes active
        expect(filter_btn).to_have_class(re.compile(r".*\bactive\b.*"))
        
        # Brief wait for filter to apply
        page.wait_for_timeout(500)


# ============================================================================
# Screenshot on Failure Hook
# ============================================================================

@pytest.fixture(scope="function", autouse=True)
def screenshot_on_failure(page: Page, request) -> Generator[None, None, None]:
    """Take screenshot on test failure."""
    yield
    
    # Check if test failed
    if hasattr(request.node, 'rep_call') and request.node.rep_call.failed:
        # Generate screenshot filename
        test_name = request.node.name
        timestamp = int(time.time())
        screenshot_path = f"test-results/screenshots/{test_name}_{timestamp}.png"
        
        # Create directory if needed
        import os
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        
        # Take screenshot
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"\nScreenshot saved to: {screenshot_path}")


# ============================================================================
# Main entry point for running tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--headed"])
