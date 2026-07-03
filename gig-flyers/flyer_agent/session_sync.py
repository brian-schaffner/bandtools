"""Shared session sync between Band Tools localStorage and Flyer Agent cookies."""

from __future__ import annotations

import html

from bridge.review import route_path

SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def agent_session_sync_script(
    *,
    redirect_to: str | None = None,
    login_path: str | None = None,
    reload: bool = False,
) -> str:
    """JS that copies session_token from localStorage into a site-wide cookie.

    Band Tools (Next.js) stores the Google session in localStorage only.
    Flyer Agent HTML routes need a cookie for normal page navigations.
    """
    login = html.escape(login_path or route_path("/agent/login"))
    session_api = html.escape(route_path("/agent/api/session"))
    if reload:
        next_action = "window.location.reload();"
    else:
        target = html.escape(redirect_to or route_path("/agent"))
        next_action = f"window.location.href = '{target}';"

    return f"""
<script>
(function() {{
  function setSessionCookie(token) {{
    document.cookie = 'session_token=' + encodeURIComponent(token)
      + '; path=/; max-age={SESSION_COOKIE_MAX_AGE}; SameSite=Lax';
  }}
  var token = localStorage.getItem('session_token') || localStorage.getItem('session_id');
  var status = document.getElementById('agent-auth-status');
  if (!token || token === 'guest-session') {{
    if (status) status.textContent = 'Not signed in yet.';
    else window.location.href = '{login}';
    return;
  }}
  setSessionCookie(token);
  fetch('{session_api}', {{ headers: {{ 'X-Session-ID': token }} }})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      if (!d.authenticated) {{
        if (status) status.textContent = 'Session expired — sign in again.';
        else window.location.href = '{login}';
        return;
      }}
      {next_action}
    }})
    .catch(function() {{
      if (status) status.textContent = 'Could not verify session.';
      else window.location.reload();
    }});
}})();
</script>"""


def render_session_bootstrap(*, redirect_to: str | None = None) -> str:
    """Minimal page shown when server has no cookie but browser may have localStorage."""
    from bridge.ui import page_close, page_head

    from flyer_agent.ui import agent_css

    return (
        page_head("Flyer Agent — Signing in", extra_css=agent_css())
        + """
  <main class="page-main">
    <div class="login-panel">
      <h1>Flyer Agent</h1>
      <p class="lead">Connecting your Band Tools session…</p>
      <p class="muted" id="agent-auth-status">Checking session…</p>
    </div>
  </main>
"""
        + agent_session_sync_script(redirect_to=redirect_to, reload=False)
        + page_close()
    )
