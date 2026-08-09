import 'package:flutter/material.dart';

import '../services/knowledge_service.dart';

class ContextualKnowledgePanel extends StatefulWidget {
  const ContextualKnowledgePanel({
    super.key,
    required this.contextId,
    required this.title,
    this.maxNotes = 3,
  });

  final String contextId;
  final String title;
  final int maxNotes;

  @override
  State<ContextualKnowledgePanel> createState() => _ContextualKnowledgePanelState();
}

class _ContextualKnowledgePanelState extends State<ContextualKnowledgePanel> {
  final _service = KnowledgeService();
  late Future<List<KnowledgeNoteSummary>> _notes;

  @override
  void initState() {
    super.initState();
    _notes = _load();
  }

  Future<List<KnowledgeNoteSummary>> _load() => _service.contextNotes(widget.contextId, limit: widget.maxNotes);

  void _refresh() => setState(() {
        _notes = _load();
      });

  Future<void> _openNote(KnowledgeNoteSummary summary) async {
    try {
      final note = await _service.note(summary.path);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => Dialog(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 820, maxHeight: 720),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.menu_book_rounded),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          note.title,
                          style: Theme.of(dialogContext).textTheme.headlineSmall,
                        ),
                      ),
                      IconButton(
                        tooltip: 'Close',
                        onPressed: () => Navigator.pop(dialogContext),
                        icon: const Icon(Icons.close_rounded),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(note.path, style: Theme.of(dialogContext).textTheme.bodySmall),
                  if (note.tags.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: note.tags.map((tag) => Chip(label: Text('#$tag'))).toList(growable: false),
                    ),
                  ],
                  const SizedBox(height: 12),
                  const Divider(),
                  const SizedBox(height: 8),
                  Expanded(
                    child: SelectionArea(
                      child: SingleChildScrollView(
                        child: Text(
                          note.content,
                          style: const TextStyle(fontFamily: 'monospace', height: 1.45),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to open Knowledge note: $error')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: FutureBuilder<List<KnowledgeNoteSummary>>(
          future: _notes,
          builder: (context, snapshot) {
            final values = snapshot.data ?? const <KnowledgeNoteSummary>[];
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.menu_book_rounded, size: 20, color: scheme.primary),
                    const SizedBox(width: 9),
                    Expanded(
                      child: Text(widget.title, style: Theme.of(context).textTheme.titleSmall),
                    ),
                    if (snapshot.connectionState == ConnectionState.waiting)
                      const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    else
                      IconButton(
                        tooltip: 'Refresh related Knowledge',
                        onPressed: _refresh,
                        icon: const Icon(Icons.refresh_rounded, size: 20),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                if (snapshot.hasError)
                  Text(
                    'Related Knowledge is unavailable.',
                    style: TextStyle(color: scheme.onSurfaceVariant),
                  )
                else if (snapshot.connectionState != ConnectionState.waiting && values.isEmpty)
                  Text(
                    'Add siris: [${widget.contextId}] or #siris/${widget.contextId} to a vault note to surface it here.',
                    style: TextStyle(color: scheme.onSurfaceVariant),
                  )
                else
                  for (final note in values.take(widget.maxNotes))
                    ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(Icons.description_outlined, size: 20),
                      title: Text(note.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                      subtitle: Text(note.path, maxLines: 1, overflow: TextOverflow.ellipsis),
                      trailing: const Icon(Icons.chevron_right_rounded),
                      onTap: () => _openNote(note),
                    ),
              ],
            );
          },
        ),
      ),
    );
  }
}
