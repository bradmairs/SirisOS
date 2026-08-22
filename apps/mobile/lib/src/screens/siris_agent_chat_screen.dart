import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/siris_agent.dart';
import '../services/ollama_status_service.dart';
import '../services/siris_agent_service.dart';
import '../services/siris_memory_service.dart';
import '../theme/app_theme.dart';

const _examplePrompts = [
  'How strong am I right now?',
  'Is it a good day to run?',
  'What have I trained this week?',
  'Are all my Docker containers healthy?',
  'What project am I currently working on?',
];

// Conversation state lives client-side, stateless per call on the backend
// (ADR 091) -- persistence is entirely local too. Capped on both ends: only
// the most recent turns are kept in storage (a chat transcript isn't meant
// to grow forever), and only a shorter recent window is actually sent as
// context on each request, so a long-lived persisted conversation can't
// silently balloon every Ollama call's token count.
const _maxStoredTurns = 200;
const _maxContextTurns = 20;
const _chatHistoryPrefsKey = 'siris_agent_chat_history_v1';

class _ChatTurn {
  const _ChatTurn({required this.role, required this.content, this.toolsUsed});

  factory _ChatTurn.fromJson(Map<String, dynamic> json) => _ChatTurn(
        role: json['role'] as String,
        content: json['content'] as String,
        toolsUsed: (json['toolsUsed'] as List<dynamic>?)?.whereType<String>().toList(growable: false),
      );

  final String role; // 'user' | 'assistant'
  final String content;
  final List<String>? toolsUsed;

  Map<String, dynamic> toJson() => {
        'role': role,
        'content': content,
        if (toolsUsed != null) 'toolsUsed': toolsUsed,
      };
}

class SirisAgentChatScreen extends StatefulWidget {
  const SirisAgentChatScreen({super.key});

  @override
  State<SirisAgentChatScreen> createState() => _SirisAgentChatScreenState();
}

class _SirisAgentChatScreenState extends State<SirisAgentChatScreen> {
  final _service = SirisAgentService();
  final _statusService = OllamaStatusService();
  final _memoryService = SirisMemoryService();
  final _input = TextEditingController();
  final _scrollController = ScrollController();
  final List<_ChatTurn> _turns = [];
  // Keyed by the assistant turn's index in _turns. Deliberately not part of
  // persisted history (ADR 100) -- a suggestion is only meaningful right
  // after its exchange happened; re-showing it after restoring a
  // conversation days later would be surprising, not helpful.
  final Map<int, List<SirisMemorySuggestion>> _memorySuggestions = {};
  late Future<OllamaStatus> _statusFuture;
  bool _sending = false;
  bool _restoredHistory = false;

  @override
  void initState() {
    super.initState();
    _statusFuture = _statusService.status();
    _restoreHistory();
  }

  Future<void> _restoreHistory() async {
    final preferences = await SharedPreferences.getInstance();
    final raw = preferences.getString(_chatHistoryPrefsKey);
    if (raw == null) {
      setState(() => _restoredHistory = true);
      return;
    }
    try {
      final decoded = jsonDecode(raw);
      if (decoded is List) {
        final restored = decoded
            .whereType<Map<String, dynamic>>()
            .map(_ChatTurn.fromJson)
            .toList(growable: false);
        if (!mounted) return;
        setState(() {
          _turns.addAll(restored);
          _restoredHistory = true;
        });
        _scrollToBottom();
        return;
      }
    } catch (_) {
      // A corrupted or outdated stored payload must not block the chat
      // screen from opening -- just start fresh, same fail-open spirit as
      // every other local-only cache in this app.
    }
    if (mounted) setState(() => _restoredHistory = true);
  }

  Future<void> _persistHistory() async {
    final preferences = await SharedPreferences.getInstance();
    final toStore = _turns.length > _maxStoredTurns
        ? _turns.sublist(_turns.length - _maxStoredTurns)
        : _turns;
    await preferences.setString(
      _chatHistoryPrefsKey,
      jsonEncode(toStore.map((turn) => turn.toJson()).toList(growable: false)),
    );
  }

  Future<void> _clearConversation() async {
    setState(() {
      _turns.clear();
      _memorySuggestions.clear();
    });
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove(_chatHistoryPrefsKey);
  }

  Future<void> _fetchMemorySuggestions({
    required int turnIndex,
    required String userMessage,
    required String assistantMessage,
  }) async {
    final suggestions = await _memoryService.suggest(
      userMessage: userMessage,
      assistantMessage: assistantMessage,
    );
    if (!mounted || suggestions.isEmpty) return;
    setState(() => _memorySuggestions[turnIndex] = suggestions);
  }

  Future<void> _saveSuggestion(int turnIndex, SirisMemorySuggestion suggestion) async {
    // Optimistically remove it first -- a slow or failed save shouldn't
    // leave a stale suggestion sitting on screen looking actionable.
    setState(() => _memorySuggestions[turnIndex]?.remove(suggestion));
    try {
      await _memoryService.create(memoryClass: suggestion.memoryClass, content: suggestion.content);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Saved to Siris Memory.'), duration: Duration(seconds: 2)),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to save memory: $error')),
      );
    }
  }

  void _dismissSuggestion(int turnIndex, SirisMemorySuggestion suggestion) {
    setState(() => _memorySuggestions[turnIndex]?.remove(suggestion));
  }

  @override
  void dispose() {
    _input.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _send([String? text]) async {
    final message = (text ?? _input.text).trim();
    if (message.isEmpty || _sending) return;
    setState(() {
      _turns.add(_ChatTurn(role: 'user', content: message));
      _sending = true;
    });
    _input.clear();
    _scrollToBottom();
    unawaited(_persistHistory());
    try {
      // Only a recent window is sent as context, independent of how long
      // the persisted, on-screen conversation has grown -- a chat restored
      // from days ago shouldn't silently balloon every request's token
      // count just because it's still visible.
      final contextTurns = _turns.length > _maxContextTurns
          ? _turns.sublist(_turns.length - _maxContextTurns)
          : _turns;
      final history =
          contextTurns.map((turn) => SirisAgentMessage(role: turn.role, content: turn.content)).toList();
      final reply = await _service.ask(history);
      if (!mounted) return;
      final assistantTurnIndex = _turns.length;
      setState(() {
        _turns.add(_ChatTurn(role: 'assistant', content: reply.answer, toolsUsed: reply.toolsUsed));
      });
      unawaited(_fetchMemorySuggestions(turnIndex: assistantTurnIndex, userMessage: message, assistantMessage: reply.answer));
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _turns.add(_ChatTurn(role: 'assistant', content: 'Something went wrong: $error'));
      });
    } finally {
      if (mounted) setState(() => _sending = false);
      _scrollToBottom();
      unawaited(_persistHistory());
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Ask Siris anything about your training, health, homelab, knowledge and '
                    'projects data -- every answer comes from a real tool call, never invented.',
                    style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
                  ),
                ),
                const SizedBox(width: 8),
                FutureBuilder<OllamaStatus>(
                  future: _statusFuture,
                  builder: (context, snapshot) {
                    final status = snapshot.data;
                    if (status == null) return const SizedBox.shrink();
                    return _OllamaStatusChip(status: status);
                  },
                ),
                if (_restoredHistory && _turns.isNotEmpty) ...[
                  const SizedBox(width: 4),
                  IconButton(
                    onPressed: _clearConversation,
                    tooltip: 'Clear conversation',
                    icon: const Icon(Icons.delete_outline_rounded, size: 20),
                    visualDensity: VisualDensity.compact,
                  ),
                ],
              ],
            ),
          ),
          Expanded(
            child: !_restoredHistory
                ? const SizedBox.shrink()
                : _turns.isEmpty
                    ? _EmptyChatState(onExampleTap: _send)
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.all(16),
                        itemCount: _turns.length,
                        itemBuilder: (context, index) => _ChatBubble(
                          turn: _turns[index],
                          suggestions: _memorySuggestions[index],
                          onSaveSuggestion: (suggestion) => _saveSuggestion(index, suggestion),
                          onDismissSuggestion: (suggestion) => _dismissSuggestion(index, suggestion),
                        ),
                      ),
          ),
          if (_sending)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: SizedBox(
                height: 16,
                width: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _input,
                    enabled: !_sending,
                    decoration: const InputDecoration(hintText: 'Ask Siris anything…'),
                    onSubmitted: (_) => _send(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  onPressed: _sending ? null : () => _send(),
                  icon: const Icon(Icons.send_rounded),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyChatState extends StatelessWidget {
  const _EmptyChatState({required this.onExampleTap});

  final ValueChanged<String> onExampleTap;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.auto_awesome_rounded, size: 40, color: AppTheme.primaryBright),
            const SizedBox(height: 12),
            Text('Ask Siris anything', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 6),
            Text(
              'Siris looks up your real SirisGym, SirisRun, Health, Homelab, Knowledge and '
              'Projects data to answer -- it never makes up a number.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: _examplePrompts
                  .map((prompt) => ActionChip(
                        label: Text(prompt),
                        onPressed: () => onExampleTap(prompt),
                      ))
                  .toList(growable: false),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChatBubble extends StatelessWidget {
  const _ChatBubble({
    required this.turn,
    this.suggestions,
    required this.onSaveSuggestion,
    required this.onDismissSuggestion,
  });

  final _ChatTurn turn;
  final List<SirisMemorySuggestion>? suggestions;
  final ValueChanged<SirisMemorySuggestion> onSaveSuggestion;
  final ValueChanged<SirisMemorySuggestion> onDismissSuggestion;

  @override
  Widget build(BuildContext context) {
    final isUser = turn.role == 'user';
    final bubbleColor = isUser ? AppTheme.primary.withValues(alpha: 0.18) : AppTheme.surfaceRaised;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          Flexible(
            child: Column(
              crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: bubbleColor,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Text(turn.content),
                ),
                if (turn.toolsUsed != null && turn.toolsUsed!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4, left: 4, right: 4),
                    child: Text(
                      'Checked: ${turn.toolsUsed!.map(_toolLabel).join(', ')}',
                      style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 11),
                    ),
                  ),
                if (suggestions != null && suggestions!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: suggestions!
                          .map((suggestion) => _MemorySuggestionChip(
                                suggestion: suggestion,
                                onSave: () => onSaveSuggestion(suggestion),
                                onDismiss: () => onDismissSuggestion(suggestion),
                              ))
                          .toList(growable: false),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  static String _toolLabel(String tool) =>
      tool.replaceFirst('get_', '').replaceAll('_', ' ');
}

class _MemorySuggestionChip extends StatelessWidget {
  const _MemorySuggestionChip({
    required this.suggestion,
    required this.onSave,
    required this.onDismiss,
  });

  final SirisMemorySuggestion suggestion;
  final VoidCallback onSave;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(top: 6),
      padding: const EdgeInsets.fromLTRB(12, 8, 4, 8),
      constraints: const BoxConstraints(maxWidth: 420),
      decoration: BoxDecoration(
        color: AppTheme.primaryBright.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.primaryBright.withValues(alpha: 0.3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const Icon(Icons.auto_awesome_rounded, size: 16, color: AppTheme.primaryBright),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Siris noticed',
                  style: TextStyle(fontSize: 10, color: scheme.onSurfaceVariant, fontWeight: FontWeight.w600),
                ),
                Text(suggestion.content, style: const TextStyle(fontSize: 13)),
              ],
            ),
          ),
          IconButton(
            onPressed: onSave,
            tooltip: 'Save to memory',
            icon: const Icon(Icons.check_circle_outline_rounded, size: 20),
            visualDensity: VisualDensity.compact,
            color: AppTheme.success,
          ),
          IconButton(
            onPressed: onDismiss,
            tooltip: 'Dismiss',
            icon: const Icon(Icons.close_rounded, size: 20),
            visualDensity: VisualDensity.compact,
            color: scheme.onSurfaceVariant,
          ),
        ],
      ),
    );
  }
}

class _OllamaStatusChip extends StatelessWidget {
  const _OllamaStatusChip({required this.status});

  final OllamaStatus status;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final IconData icon;
    final String label;
    final Color color;
    if (!status.configured) {
      icon = Icons.settings_outlined;
      label = 'Ollama not configured';
      color = scheme.onSurfaceVariant;
    } else if (!status.reachable) {
      icon = Icons.cloud_off_rounded;
      label = 'Ollama unreachable';
      color = scheme.error;
    } else if (!status.modelAvailable) {
      icon = Icons.warning_amber_rounded;
      label = 'Model "${status.model}" not found';
      color = scheme.error;
    } else {
      icon = Icons.check_circle_rounded;
      label = status.model ?? 'Ollama online';
      color = scheme.primary;
    }
    return Chip(
      avatar: Icon(icon, size: 16, color: color),
      label: Text(label, style: TextStyle(color: color, fontSize: 12)),
      visualDensity: VisualDensity.compact,
    );
  }
}
