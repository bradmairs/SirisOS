import 'dart:async';

import 'package:flutter/material.dart';

import '../models/search_result.dart';
import '../services/knowledge_service.dart';
import '../services/search_service.dart';

class GlobalSearchScreen extends StatefulWidget {
  const GlobalSearchScreen({required this.onOpenTarget, super.key});

  final void Function(String target) onOpenTarget;

  @override
  State<GlobalSearchScreen> createState() => _GlobalSearchScreenState();
}

class _GlobalSearchScreenState extends State<GlobalSearchScreen> {
  final _controller = TextEditingController();
  final _service = SearchService();
  final _knowledgeService = KnowledgeService();
  Timer? _debounce;
  List<SirisSearchResult> _results = const [];
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _changed(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () => _search(value));
  }

  Future<void> _search(String value) async {
    final query = value.trim();
    if (query.length < 2) {
      if (mounted) {
        setState(() {
          _results = const [];
          _loading = false;
          _error = null;
        });
      }
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await _service.search(query);
      if (mounted && _controller.text.trim() == query) {
        setState(() {
          _results = results;
          _loading = false;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = error.toString();
        });
      }
    }
  }

  IconData _icon(String module) => switch (module) {
        'homelab' => Icons.dns_rounded,
        'running' => Icons.directions_run_rounded,
        'gym' => Icons.fitness_center_rounded,
        'activity' => Icons.notifications_rounded,
        'knowledge' => Icons.menu_book_rounded,
        'projects' => Icons.folder_rounded,
        'engineering' => Icons.engineering_rounded,
        'siris' => Icons.auto_awesome_rounded,
        _ => Icons.search_rounded,
      };

  Future<void> _open(SirisSearchResult result) async {
    if (result.module == 'knowledge' && result.referenceId != null) {
      try {
        final note = await _knowledgeService.note(result.referenceId!);
        if (!mounted) return;
        await showDialog<void>(
          context: context,
          builder: (context) => Dialog(
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
                        Expanded(child: Text(note.title, style: Theme.of(context).textTheme.headlineSmall)),
                        IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close_rounded)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(note.path, style: Theme.of(context).textTheme.bodySmall),
                    if (note.tags.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Wrap(spacing: 6, runSpacing: 6, children: note.tags.map((tag) => Chip(label: Text('#$tag'))).toList()),
                    ],
                    const SizedBox(height: 12),
                    const Divider(),
                    const SizedBox(height: 8),
                    Expanded(
                      child: SelectionArea(
                        child: SingleChildScrollView(
                          child: Text(note.content, style: const TextStyle(fontFamily: 'monospace', height: 1.45)),
                        ),
                      ),
                    ),
                    const Divider(),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton.icon(
                        onPressed: () {
                          Navigator.pop(context);
                          Navigator.pop(this.context);
                          widget.onOpenTarget('knowledge');
                        },
                        icon: const Icon(Icons.open_in_new_rounded),
                        label: const Text('Open Knowledge'),
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
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Unable to open note: $error')));
      }
      return;
    }

    Navigator.pop(context);
    widget.onOpenTarget(result.target);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Search SirisOS')),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
              child: SearchBar(
                controller: _controller,
                hintText: 'Notes, projects, calculations, standards, memory, containers…',
                leading: const Icon(Icons.search_rounded),
                trailing: [
                  if (_controller.text.isNotEmpty)
                    IconButton(
                      onPressed: () {
                        _controller.clear();
                        _changed('');
                        setState(() {});
                      },
                      icon: const Icon(Icons.close_rounded),
                    ),
                ],
                onChanged: (value) {
                  _changed(value);
                  setState(() {});
                },
                onSubmitted: _search,
              ),
            ),
            if (_loading) const LinearProgressIndicator(),
            Expanded(
              child: Builder(
                builder: (context) {
                  if (_error != null) {
                    return Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Text(_error!, textAlign: TextAlign.center),
                      ),
                    );
                  }
                  if (_controller.text.trim().length < 2) {
                    return const _SearchHint();
                  }
                  if (!_loading && _results.isEmpty) {
                    return const Center(
                      child: Text('No matching SirisOS items found.'),
                    );
                  }
                  return ListView.separated(
                    padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
                    itemCount: _results.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final result = _results[index];
                      return Card(
                        child: ListTile(
                          leading: CircleAvatar(
                            child: Icon(_icon(result.module)),
                          ),
                          title: Text(result.title),
                          subtitle: Text(
                            result.subtitle,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                          trailing: const Icon(Icons.chevron_right_rounded),
                          onTap: () => _open(result),
                        ),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SearchHint extends StatelessWidget {
  const _SearchHint();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.manage_search_rounded,
              size: 58,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Text(
              'Search everything',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Search Knowledge notes, Projects, saved Engineering calculations, Standards, Siris Memory, Docker '
              'containers, running history, gym workouts and recent SirisOS activity.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
