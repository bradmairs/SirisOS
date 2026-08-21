import 'package:flutter/material.dart';

import '../models/siris_agent.dart';
import '../services/ollama_status_service.dart';
import '../services/siris_agent_service.dart';
import '../theme/app_theme.dart';

const _examplePrompts = [
  'How strong am I right now?',
  'Is it a good day to run?',
  'What have I trained this week?',
  'Are all my Docker containers healthy?',
];

class _ChatTurn {
  const _ChatTurn({required this.role, required this.content, this.toolsUsed});

  final String role; // 'user' | 'assistant'
  final String content;
  final List<String>? toolsUsed;
}

class SirisAgentChatScreen extends StatefulWidget {
  const SirisAgentChatScreen({super.key});

  @override
  State<SirisAgentChatScreen> createState() => _SirisAgentChatScreenState();
}

class _SirisAgentChatScreenState extends State<SirisAgentChatScreen> {
  final _service = SirisAgentService();
  final _statusService = OllamaStatusService();
  final _input = TextEditingController();
  final _scrollController = ScrollController();
  final List<_ChatTurn> _turns = [];
  late Future<OllamaStatus> _statusFuture;
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    _statusFuture = _statusService.status();
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
    try {
      final history =
          _turns.map((turn) => SirisAgentMessage(role: turn.role, content: turn.content)).toList();
      final reply = await _service.ask(history);
      if (!mounted) return;
      setState(() {
        _turns.add(_ChatTurn(role: 'assistant', content: reply.answer, toolsUsed: reply.toolsUsed));
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _turns.add(_ChatTurn(role: 'assistant', content: 'Something went wrong: $error'));
      });
    } finally {
      if (mounted) setState(() => _sending = false);
      _scrollToBottom();
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
                    'Ask Siris anything about your training, health and homelab data -- every '
                    'answer comes from a real tool call, never invented.',
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
              ],
            ),
          ),
          Expanded(
            child: _turns.isEmpty
                ? _EmptyChatState(onExampleTap: _send)
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(16),
                    itemCount: _turns.length,
                    itemBuilder: (context, index) => _ChatBubble(turn: _turns[index]),
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
              'Siris looks up your real SirisGym, SirisRun, Health and Homelab data to '
              'answer -- it never makes up a number.',
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
  const _ChatBubble({required this.turn});

  final _ChatTurn turn;

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
