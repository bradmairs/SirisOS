import 'package:flutter/material.dart';

import '../services/siris_memory_service.dart';

class SirisMemoryScreen extends StatefulWidget {
  const SirisMemoryScreen({super.key});

  @override
  State<SirisMemoryScreen> createState() => _SirisMemoryScreenState();
}

class _SirisMemoryScreenState extends State<SirisMemoryScreen> {
  final _service = SirisMemoryService();
  SirisMemoryClass? _filter;
  late Future<List<SirisMemoryRecord>> _memory;

  @override
  void initState() {
    super.initState();
    _memory = _service.list();
  }

  void _refresh() => setState(() {
        _memory = _service.list(memoryClass: _filter);
      });

  void _setFilter(SirisMemoryClass? value) {
    setState(() => _filter = value);
    _refresh();
  }

  Future<void> _addMemory() async {
    final result = await showDialog<_AddMemoryResult>(
      context: context,
      builder: (_) => const _AddMemoryDialog(),
    );
    if (result == null || !mounted) return;
    try {
      await _service.create(
        memoryClass: result.memoryClass,
        content: result.content,
        source: result.source,
      );
      if (!mounted) return;
      _refresh();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to save memory: $error')),
      );
    }
  }

  Future<void> _delete(SirisMemoryRecord record) async {
    try {
      await _service.delete(record.id);
      if (!mounted) return;
      _refresh();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to delete memory: $error')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Row(
            children: [
              Expanded(
                child: Text('Siris Memory', style: Theme.of(context).textTheme.headlineSmall),
              ),
              FilledButton.icon(
                onPressed: _addMemory,
                icon: const Icon(Icons.add_rounded),
                label: const Text('Remember'),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Facts, preferences, episodes, decisions, observations and conversation notes Siris '
            'accumulates over time — its own understanding, distinct from Knowledge documents and '
            'Project relationships.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 40,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                _FilterChip(label: 'All', selected: _filter == null, onTap: () => _setFilter(null)),
                for (final memoryClass in SirisMemoryClass.values)
                  Padding(
                    padding: const EdgeInsets.only(left: 8),
                    child: _FilterChip(
                      label: memoryClass.label,
                      selected: _filter == memoryClass,
                      onTap: () => _setFilter(memoryClass),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          FutureBuilder<List<SirisMemoryRecord>>(
            future: _memory,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(
                  child: Padding(
                    padding: EdgeInsets.all(32),
                    child: CircularProgressIndicator(),
                  ),
                );
              }
              if (snapshot.hasError) {
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Text('Unable to load Siris memory: ${snapshot.error}'),
                  ),
                );
              }
              final records = snapshot.requireData;
              if (records.isEmpty) {
                return const Card(
                  child: Padding(
                    padding: EdgeInsets.all(18),
                    child: Text(
                      'Nothing remembered yet. Add a fact, preference or decision worth Siris keeping track of.',
                    ),
                  ),
                );
              }
              return Column(
                children: [
                  for (final record in records)
                    Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Wrap(
                                    spacing: 8,
                                    runSpacing: 4,
                                    crossAxisAlignment: WrapCrossAlignment.center,
                                    children: [
                                      _MemoryClassBadge(memoryClass: record.memoryClass),
                                      Text(
                                        record.createdAt.toLocal().toString().split('.').first,
                                        style: Theme.of(context).textTheme.bodySmall,
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 8),
                                  Text(record.content),
                                  if (record.source != null) ...[
                                    const SizedBox(height: 6),
                                    Text(
                                      record.source!,
                                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                            fontStyle: FontStyle.italic,
                                          ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                            IconButton(
                              tooltip: 'Forget',
                              icon: const Icon(Icons.delete_outline_rounded),
                              onPressed: () => _delete(record),
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(label: Text(label), selected: selected, onSelected: (_) => onTap());
  }
}

class _MemoryClassBadge extends StatelessWidget {
  const _MemoryClassBadge({required this.memoryClass});

  final SirisMemoryClass memoryClass;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: scheme.primaryContainer,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        memoryClass.label,
        style: TextStyle(
          color: scheme.onPrimaryContainer,
          fontSize: 12,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _AddMemoryResult {
  const _AddMemoryResult({required this.memoryClass, required this.content, this.source});
  final SirisMemoryClass memoryClass;
  final String content;
  final String? source;
}

class _AddMemoryDialog extends StatefulWidget {
  const _AddMemoryDialog();

  @override
  State<_AddMemoryDialog> createState() => _AddMemoryDialogState();
}

class _AddMemoryDialogState extends State<_AddMemoryDialog> {
  SirisMemoryClass _memoryClass = SirisMemoryClass.fact;
  final _content = TextEditingController();
  final _source = TextEditingController();

  @override
  void dispose() {
    _content.dispose();
    _source.dispose();
    super.dispose();
  }

  void _submit() {
    final content = _content.text.trim();
    if (content.isEmpty) return;
    Navigator.pop(
      context,
      _AddMemoryResult(
        memoryClass: _memoryClass,
        content: content,
        source: _source.text.trim().isEmpty ? null : _source.text.trim(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Remember something'),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            DropdownButtonFormField<SirisMemoryClass>(
              initialValue: _memoryClass,
              decoration: const InputDecoration(labelText: 'Type', border: OutlineInputBorder()),
              items: [
                for (final memoryClass in SirisMemoryClass.values)
                  DropdownMenuItem(value: memoryClass, child: Text(memoryClass.label)),
              ],
              onChanged: (value) {
                if (value != null) setState(() => _memoryClass = value);
              },
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _content,
              autofocus: true,
              minLines: 2,
              maxLines: 5,
              decoration: const InputDecoration(labelText: 'What should Siris remember?', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _source,
              decoration: const InputDecoration(
                labelText: 'Source (optional)',
                hintText: 'e.g. Project: Sydney Water rising main',
                border: OutlineInputBorder(),
              ),
              onSubmitted: (_) => _submit(),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _submit, child: const Text('Save')),
      ],
    );
  }
}
