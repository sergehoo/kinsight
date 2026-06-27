from django.urls import path

from .views import (
    ActionApproveView,
    ActionListView,
    ActionRejectView,
    ChatView,
    ConversationDetailView,
    ConversationListView,
    ToolExecuteView,
    ToolsListView,
)

urlpatterns = [
    path("chat/", ChatView.as_view(), name="ai-chat"),
    path("conversations/", ConversationListView.as_view(), name="ai-conversations"),
    path("conversations/<uuid:pk>/", ConversationDetailView.as_view(), name="ai-conversation-detail"),
    path("tools/", ToolsListView.as_view(), name="ai-tools"),
    path("tools/execute/", ToolExecuteView.as_view(), name="ai-tool-execute"),
    path("actions/", ActionListView.as_view(), name="ai-actions"),
    path("actions/<uuid:pk>/approve/", ActionApproveView.as_view(), name="ai-action-approve"),
    path("actions/<uuid:pk>/reject/", ActionRejectView.as_view(), name="ai-action-reject"),
]
