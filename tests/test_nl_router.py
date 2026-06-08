from shell_nl_router import route_natural_command
from shell_tool_catalog import discover_tool_catalog


def test_natural_text_count_route():
    route = route_natural_command("count words in hello shell world")

    assert route["tool"] == "shell_text_tools:text_count_tool"
    assert route["args"] == {"text": "hello shell world"}


def test_natural_math_route():
    route = route_natural_command("what is 2 + 3 * 4")

    assert route["tool"] == "shell_calculator:calculate_tool"
    assert route["args"] == {"expression": "2 + 3 * 4"}


def test_natural_unit_alias_route():
    route = route_natural_command("convert 2 meter to centimeter")

    assert route["tool"] == "shell_calculator:unit_convert_tool"
    assert route["args"] == {"value": 2, "from_unit": "m", "to_unit": "cm"}


def test_natural_agent_route():
    route = route_natural_command("developer agent fix the login bug")

    assert route["tool"] == "shell_agents:developer_agent_tool"
    assert route["kind"] == "agent"
    assert route["args"] == {"task": "fix the login bug"}


def test_generic_hinglish_code_request_routes_to_developer_agent():
    route = route_natural_command("python code likho fibonacci function")

    assert route["tool"] == "shell_agents:developer_agent_tool"
    assert route["kind"] == "agent"
    assert route["args"] == {"task": "python code likho fibonacci function"}


def test_generic_english_code_request_routes_to_developer_agent():
    route = route_natural_command("write code for sorting a list in javascript")

    assert route["tool"] == "shell_agents:developer_agent_tool"
    assert route["kind"] == "agent"
    assert route["args"] == {"task": "write code for sorting a list in javascript"}


def test_natural_list_tools_route():
    route = route_natural_command("show all tools")

    assert route["tool"] == "shell_agent_tools:list_all_tools"
    assert route["kind"] == "tool"


def test_natural_search_route_uses_cross_platform_url_tool():
    route = route_natural_command("search google for pyqt qthread cleanup")

    assert route["tool"] == "shell_desktop_tools:open_url_tool"
    assert route["kind"] == "tool"
    assert "https://www.google.com/search" in route["args"]["url"]
    assert "pyqt+qthread+cleanup" in route["args"]["url"]


def test_natural_youtube_song_play_route_does_not_use_terminal():
    route = route_natural_command("youtube pe palpal song play karo")

    assert route["tool"] == "shell_browser_CTRL:play_youtube_video"
    assert route["kind"] == "tool"
    assert route["args"] == {"query": "palpal song", "number": 1}


def test_generic_song_play_route_uses_youtube_player():
    route = route_natural_command("song play karo")

    assert route["tool"] == "shell_browser_CTRL:play_youtube_video"
    assert route["kind"] == "tool"
    assert route["args"] == {"query": "song", "number": 1}


def test_shell_address_youtube_song_play_route_does_not_use_terminal():
    route = route_natural_command("shell se youtube pe palpal song play karo")

    assert route["tool"] == "shell_browser_CTRL:play_youtube_video"
    assert route["kind"] == "tool"
    assert route["args"] == {"query": "palpal song", "number": 1}


def test_direct_website_build_route_uses_code_engine_not_chat_fallback():
    route = route_natural_command("website banao landing page for bakery")

    assert route["tool"] == "shell_code_engine:create_fullstack_app_tool"
    assert route["kind"] == "tool"
    assert route["args"]["project_name"] == "bakery"
    assert route["args"]["app_type"].startswith("Build a polished responsive website for bakery")
    assert "Do not echo the request text" in route["args"]["app_type"]


def test_direct_app_build_route_uses_code_engine_not_agent_chat():
    route = route_natural_command("todo app banao with login")

    assert route["tool"] == "shell_code_engine:create_fullstack_app_tool"
    assert route["kind"] == "tool"
    assert route["args"]["project_name"] == "todo_with_login"
    assert route["args"]["app_type"].startswith("Build a full-stack app for todo login")
    assert "Do not echo the request text" in route["args"]["app_type"]


def test_login_page_html_save_routes_to_working_user_file_not_developer_agent():
    route = route_natural_command("mere liyye login page banao html main or osse save kardo")

    assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
    assert route["kind"] == "tool"
    assert route["args"]["filename"] == "login_page.html"
    assert route["args"]["destination"] == "desktop"
    assert route["args"]["file_type"] == "html"
    assert "standalone HTML login page" in route["args"]["content_request"]
    assert "client-side validation" in route["args"]["content_request"]


def test_login_page_html_working_prompt_routes_without_explicit_create_word():
    route = route_natural_command("mere liyye login page html ok voh bhi working honna chahiye ok")

    assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
    assert route["args"]["filename"] == "login_page.html"
    assert route["args"]["destination"] == "desktop"
    assert route["args"]["file_type"] == "html"


def test_website_login_page_save_to_desktop_prefers_standalone_html_file():
    route = route_natural_command("mere liye website ka login page banao or desktop pe save kar do")

    assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
    assert route["args"]["filename"] == "login_page.html"
    assert route["args"]["destination"] == "desktop"
    assert route["args"]["file_type"] == "html"


def test_open_instagram_in_chrome_uses_url_tool():
    route = route_natural_command("mere liye chrome main instagram open karo")

    assert route["tool"] == "shell_desktop_tools:open_url_tool"
    assert route["kind"] == "tool"
    assert route["args"] == {"url": "https://www.instagram.com/"}


def test_direct_game_build_route_uses_playable_game_builder():
    route = route_natural_command("snake game banao")

    assert route["tool"] == "shell_game_builder:build_game_tool"
    assert route["kind"] == "tool"
    assert route["args"] == {"game": "snake", "custom_features": ""}


def test_direct_tetris_game_build_route_keeps_known_template_fast_path():
    route = route_natural_command("make a playable tetris game with keyboard controls")

    assert route["tool"] == "shell_game_builder:build_game_tool"
    assert route["args"] == {"game": "tetris", "custom_features": ""}


def test_voice_status_route_uses_real_voice_runtime_status_tool():
    route = route_natural_command("voice status check")

    assert route["tool"] == "shell_neural_voice:shell_streaming_voice_status_tool"
    assert route["kind"] == "tool"


def test_autonomous_run_route_wraps_inner_goal():
    route = route_natural_command("autonomous run open calculator")

    assert route["tool"] == "shell_autonomous_agent:autonomous_goal_run_tool"
    assert route["kind"] == "tool"
    assert route["args"] == {"goal": "open calculator", "dry_run": False, "learn": True, "verify": True, "auto_repair": True}


def test_autonomous_preview_route_uses_dry_run():
    route = route_natural_command("agent preview snake game banao")

    assert route["tool"] == "shell_autonomous_agent:autonomous_goal_run_tool"
    assert route["args"] == {"goal": "snake game banao", "dry_run": True, "learn": False, "verify": False, "auto_repair": False}


def test_autonomous_status_and_skill_routes():
    status = route_natural_command("autonomy status")
    skills = route_natural_command("show learned skills")

    assert status["tool"] == "shell_autonomous_agent:autonomous_goal_status_tool"
    assert status["args"] == {"task_id": "", "limit": 5}
    assert skills["tool"] == "shell_autonomous_agent:autonomous_skill_list_tool"
    assert skills["args"] == {"query": "", "limit": 10}


def test_autonomous_resume_route():
    route = route_natural_command("autonomy resume abc123def456")

    assert route["tool"] == "shell_autonomous_agent:autonomous_goal_resume_tool"
    assert route["args"] == {"task_id": "abc123def456", "dry_run": False, "learn": True, "verify": True, "auto_repair": True}


def test_hinglish_photo_generation_routes_to_image_tool():
    route = route_natural_command("neon shell city ki photo banao")

    assert route["tool"] == "shell_image_ai:generate_image_tool"
    assert route["kind"] == "tool"
    assert route["args"]["description"] == "neon shell city"
    assert route["args"]["quality"] == "excellent"
    assert route["args"]["use_cache"] is False
    assert route["args"]["force_fresh"] is True


def test_image_generate_phrase_with_app_words_stays_image_tool():
    route = route_natural_command("simple shell ai dashboard icon image generate karo")

    assert route["tool"] == "shell_image_ai:generate_image_tool"
    assert route["kind"] == "tool"
    assert route["args"]["description"] == "simple shell ai dashboard icon"


def test_speechy_photo_generate_phrase_routes_to_image_tool():
    route = route_natural_command("photo generate karo quantum battery ki ok")

    assert route["tool"] == "shell_image_ai:generate_image_tool"
    assert route["args"]["description"] == "quantum battery ki"


def test_misspelled_photo_generate_phrase_routes_to_image_tool():
    route = route_natural_command("mere liye koi cat ke photo ganarete karke do ok")

    assert route["tool"] == "shell_image_ai:generate_image_tool"
    assert route["args"]["description"] == "cat"
    assert route["args"]["force_fresh"] is True


def test_hinglish_deep_research_routes_to_research_agent():
    route = route_natural_command("AI chips ke bare mein deep recerch karo")

    assert route["tool"] == "shell_agents:research_agent_tool"
    assert route["kind"] == "agent"
    assert route["args"]["task"] == "AI chips"


def test_natural_click_route_uses_cross_platform_desktop_tool():
    route = route_natural_command("click 120 340")

    assert route["tool"] == "shell_desktop_tools:desktop_click_tool"
    assert route["kind"] == "tool"
    assert route["args"] == {"x": 120, "y": 340, "button": "left"}


def test_natural_screenshot_route_uses_cross_platform_screenshot_tool():
    route = route_natural_command("take screenshot")

    assert route["tool"] == "shell_screenshot:take_screenshot_tool"
    assert route["kind"] == "tool"
    assert route["args"]["filename"] == "shell_screenshot"


def test_natural_open_app_route_is_cross_platform_tool():
    route = route_natural_command("open calculator")

    assert route["tool"] == "shell_window_CTRL:open_app"
    assert route["kind"] == "tool"
    assert route["args"] == {"app_title": "calculator"}


def test_natural_close_app_route_is_cross_platform_tool():
    route = route_natural_command("close calculator")

    assert route["tool"] == "shell_window_CTRL:close_app"
    assert route["kind"] == "tool"
    assert route["args"] == {"window_title": "calculator"}


def test_shell_desktop_folder_create_open_route():
    route = route_natural_command("Shell, create a folder called ‘Reels Export’ on Desktop and open it.")

    assert route["tool"] == "shell_windows_workflows:create_desktop_folder_tool"
    assert route["kind"] == "tool"
    assert route["args"] == {"folder_name": "Reels Export", "open_folder": True}


def test_shell_downloads_setups_pdfs_route():
    route = route_natural_command("Shell, organize my Downloads: move ZIP files to a ‘Setups’ folder and PDFs to PDFs.")

    assert route["tool"] == "shell_windows_workflows:organize_downloads_setups_pdfs_tool"
    assert route["kind"] == "tool"
    assert route["args"]["zip_folder"] == "Setups"
    assert route["args"]["pdf_folder"] == "PDFs"
    assert route["args"]["dry_run"] is False


def test_shell_work_session_route_opens_apps_without_developer_agent():
    route = route_natural_command("Shell, I’m starting work. Open VS Code, Chrome with my three dev tabs, and Spotify")

    assert route["tool"] == "shell_windows_workflows:open_work_session_tool"
    assert route["kind"] == "tool"
    assert route["args"]["include_vscode"] is True
    assert route["args"]["include_chrome"] is True
    assert route["args"]["include_spotify"] is True
    assert len(route["args"]["chrome_urls"]) == 3


def test_shell_high_cpu_route_reviews_instead_of_killing_processes():
    route = route_natural_command("Shell, open Task Manager and close all high-CPU background apps")

    assert route["tool"] == "shell_windows_workflows:open_task_manager_high_cpu_review_tool"
    assert route["kind"] == "tool"
    assert route["args"] == {"open_task_manager": True}


def test_shell_focus_assist_route_opens_settings_with_duration():
    route = route_natural_command("Shell, turn on Focus Assist for 30 minutes")

    assert route["tool"] == "shell_windows_workflows:open_focus_assist_tool"
    assert route["kind"] == "tool"
    assert route["args"] == {"minutes": 30}


def test_shell_whatsapp_spotify_route_is_combined_workflow():
    route = route_natural_command("Shell, open WhatsApp Desktop and Spotify side by side")

    assert route["tool"] == "shell_windows_workflows:open_whatsapp_spotify_side_by_side_tool"
    assert route["kind"] == "tool"


def test_shell_photos_screenshots_slideshow_route():
    route = route_natural_command("Shell, open Photos and start a slideshow of my last screenshots")

    assert route["tool"] == "shell_windows_workflows:open_recent_screenshots_slideshow_tool"
    assert route["kind"] == "tool"


def test_shell_screen_comfort_route():
    route = route_natural_command("Shell, reduce brightness and enable Night Light")

    assert route["tool"] == "shell_windows_workflows:screen_comfort_tool"
    assert route["kind"] == "tool"
    assert route["args"] == {"brightness_level": 40, "enable_night_light": True}


def test_natural_workspace_create_file_route():
    route = route_natural_command("create file notes.md with content hello shell")

    assert route["tool"] == "shell_workspace_tools:create_workspace_file_tool"
    assert route["kind"] == "tool"
    assert route["args"] == {"path": "notes.md", "content": "hello shell", "overwrite": False}


def test_natural_desktop_file_save_route():
    route = route_natural_command("notes.txt desktop pe save karo with content hello shell")

    assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
    assert route["kind"] == "tool"
    assert route["args"]["filename"] == "notes.txt"
    assert route["args"]["content"] == "hello shell"
    assert route["args"]["destination"] == "desktop"
    assert route["args"]["file_type"] == "txt"
    assert route["args"]["overwrite"] is False
    assert route["args"]["content_request"] == "Write useful file content about hello shell."


def test_natural_desktop_pdf_save_route():
    route = route_natural_command("quantum battery ke bare mein pdf bana ke desktop pe save karo")

    assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
    assert route["kind"] == "tool"
    assert route["args"]["destination"] == "desktop"
    assert route["args"]["file_type"] == "pdf"
    assert route["args"]["content"] == "quantum battery"
    assert route["args"]["content_request"] == "Write a polished PDF document about quantum battery."


def test_natural_pdf_save_without_destination_defaults_to_documents():
    route = route_natural_command("AI tools ke bare mein pdf bana do")

    assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
    assert route["kind"] == "tool"
    assert route["args"]["destination"] == "documents"
    assert route["args"]["file_type"] == "pdf"
    assert route["args"]["content"] == "AI tools"
    assert route["args"]["content_request"] == "Write a polished PDF document about AI tools."


def test_pdf_summary_about_full_app_stays_document_route():
    route = route_natural_command("Make a PDF summary of this full app architecture")

    assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
    assert route["kind"] == "tool"
    assert route["args"]["destination"] == "documents"
    assert route["args"]["file_type"] == "pdf"


def test_natural_movie_script_pdf_route_keeps_topic_and_requests_script_content():
    route = route_natural_command("movie script ka pdf banao")

    assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
    assert route["kind"] == "tool"
    assert route["args"]["destination"] == "documents"
    assert route["args"]["file_type"] == "pdf"
    assert route["args"]["content"] == "movie script"
    assert route["args"]["content_request"] == "Write an original movie script about movie script."


def test_hinglish_movie_script_pdf_typo_desktop_keeps_topic_and_destination():
    route = route_natural_command("mere liye script likho movie ki or han osse pdf main save karo ok dexdop pe")

    assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
    assert route["kind"] == "tool"
    assert route["args"]["filename"] == "movie_script.pdf"
    assert route["args"]["destination"] == "desktop"
    assert route["args"]["file_type"] == "pdf"
    assert route["args"]["content"] == "movie script"
    assert route["args"]["content_request"] == "Write an original movie script about movie script."


def test_natural_workspace_read_file_route():
    route = route_natural_command("read notes.md")

    assert route["tool"] == "shell_workspace_tools:read_workspace_file_tool"
    assert route["kind"] == "tool"
    assert route["args"] == {"path": "notes.md"}


def test_natural_workspace_list_files_route():
    route = route_natural_command("show workspace files")

    assert route["tool"] == "shell_workspace_tools:list_workspace_files_tool"
    assert route["kind"] == "tool"
    assert route["args"] == {"limit": 200}


def test_email_status_route_prevents_fake_sent_claims():
    route = route_natural_command("email kyun nahi ho raha hai")

    assert route["tool"] == "shell_email_tool:email_setup_status_tool"
    assert route["kind"] == "tool"


def test_email_login_test_route():
    route = route_natural_command("email login test karo")

    assert route["tool"] == "shell_email_tool:email_smtp_login_test_tool"
    assert route["kind"] == "tool"


def test_email_send_route_uses_real_email_tool():
    route = route_natural_command(
        "send email to user@example.com subject Test body Hello from Shell"
    )

    assert route["tool"] == "shell_email_tool:send_email_tool"
    assert route["args"]["recipient"] == "user@example.com"
    assert route["args"]["subject"] == "Test"
    assert route["args"]["body"] == "Hello from Shell"


def test_email_send_route_catches_address_without_email_word():
    route = route_natural_command(
        "zestsking@gmail.com par bhejo subject Test body Hello"
    )

    assert route["tool"] == "shell_email_tool:send_email_tool"
    assert route["args"]["recipient"] == "zestsking@gmail.com"


def test_pdf_email_without_file_path_does_not_send_empty_mail():
    route = route_natural_command("pdf ko zestsking@gmail.com par bhejo")

    assert route["tool"] == "shell_email_tool:email_setup_status_tool"


def test_pdf_email_with_attachment_routes_attachment():
    route = route_natural_command(
        'send email to user@example.com attach "Mastering Command Line Interface.pdf" body Please see attached'
    )

    assert route["tool"] == "shell_email_tool:send_email_tool"
    assert route["args"]["attachments"] == "Mastering Command Line Interface.pdf"
    assert route["args"]["body"] == "Please see attached"


def test_telegram_status_route():
    route = route_natural_command("telegram bot status")

    assert route["tool"] == "shell_telegram:telegram_bot_status"
    assert route["kind"] == "tool"


def test_cross_platform_open_close_tools_are_ready_on_current_platform():
    from core.tools.registry import enrich_catalog

    rows = [
        row for row in discover_tool_catalog()
        if row["id"] in {
            "shell_window_CTRL:open_app",
            "shell_window_CTRL:close_app",
            "shell_desktop_tools:open_url_tool",
            "shell_desktop_tools:desktop_click_tool",
            "shell_browser_CTRL:play_youtube_video",
            "shell_screenshot:take_screenshot_tool",
        }
    ]
    enriched = enrich_catalog(rows)

    assert {row["id"] for row in enriched} == {
        "shell_window_CTRL:open_app",
        "shell_window_CTRL:close_app",
        "shell_desktop_tools:open_url_tool",
        "shell_desktop_tools:desktop_click_tool",
        "shell_browser_CTRL:play_youtube_video",
        "shell_screenshot:take_screenshot_tool",
    }
    assert all(row["readiness"]["ok"] is True for row in enriched)
