import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/engineering_standards_service.dart';
import '../services/sirishydro_service.dart';
import '../widgets/standard_page_dialog.dart';

class SirisHydroScreen extends StatefulWidget {
  const SirisHydroScreen({super.key});

  @override
  State<SirisHydroScreen> createState() => _SirisHydroScreenState();
}

class _SirisHydroScreenState extends State<SirisHydroScreen> {
  final _service = SirisHydroService();
  final _question = TextEditingController();
  Future<SirisHydroEvidencePacket>? _result;

  @override
  void dispose() {
    _question.dispose();
    super.dispose();
  }

  void _retrieve() {
    final value = _question.text.trim();
    if (value.length < 2) return;
    setState(() {
      _result = _service.retrieveEvidence(value);
    });
  }

  void _askAgain(String question) {
    _question.text = question;
    _retrieve();
  }

  Future<void> _openHistory() async {
    final selected = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (_) => _HistorySheet(service: _service),
    );
    if (selected != null) _askAgain(selected);
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
                child: Text('SirisHydro', style: Theme.of(context).textTheme.headlineSmall),
              ),
              IconButton(
                tooltip: 'Past questions',
                onPressed: _openHistory,
                icon: const Icon(Icons.history_rounded),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Evidence-first engineering retrieval from your private standards library. When a local Ollama model is configured, SirisHydro also synthesizes a grounded, cited answer from the retrieved evidence.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _question,
            minLines: 2,
            maxLines: 5,
            onSubmitted: (_) => _retrieve(),
            decoration: InputDecoration(
              labelText: 'Engineering question',
              hintText: 'e.g. What minimum cover is required for an RCP under a road?',
              border: const OutlineInputBorder(),
              suffixIcon: IconButton(
                tooltip: 'Find evidence',
                onPressed: _retrieve,
                icon: const Icon(Icons.search_rounded),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton.icon(
              onPressed: _retrieve,
              icon: const Icon(Icons.manage_search_rounded),
              label: const Text('Find evidence'),
            ),
          ),
          const SizedBox(height: 20),
          if (_result == null)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(18),
                child: Text(
                  'Ask a question to retrieve the strongest matching source pages. SirisHydro will not invent a standards requirement when the library does not support it.',
                ),
              ),
            )
          else
            FutureBuilder<SirisHydroEvidencePacket>(
              future: _result,
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
                      child: Text('Unable to retrieve evidence: ${snapshot.error}'),
                    ),
                  );
                }
                final packet = snapshot.requireData;
                return _EvidencePacketView(packet: packet);
              },
            ),
        ],
      ),
    );
  }
}

class _HistorySheet extends StatefulWidget {
  const _HistorySheet({required this.service});

  final SirisHydroService service;

  @override
  State<_HistorySheet> createState() => _HistorySheetState();
}

class _HistorySheetState extends State<_HistorySheet> {
  late Future<List<SirisHydroHistoryRecord>> _history;

  @override
  void initState() {
    super.initState();
    _history = widget.service.history();
  }

  void _refresh() => setState(() {
        _history = widget.service.history();
      });

  Future<void> _delete(SirisHydroHistoryRecord record) async {
    try {
      await widget.service.deleteHistoryRecord(record.id);
      _refresh();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to delete record: $error')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      heightFactor: 0.85,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Past questions', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 4),
            Text(
              'SirisHydro remembers what you asked, what it found, and any synthesized answer.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 12),
            Expanded(
              child: FutureBuilder<List<SirisHydroHistoryRecord>>(
                future: _history,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return Center(child: Text('Unable to load history: ${snapshot.error}'));
                  }
                  final records = snapshot.requireData;
                  if (records.isEmpty) {
                    return const Center(child: Text('No questions asked yet.'));
                  }
                  return ListView.separated(
                    itemCount: records.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final record = records[index];
                      return ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(
                          record.sufficientEvidence ? Icons.verified_rounded : Icons.warning_amber_rounded,
                        ),
                        title: Text(record.question),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(record.createdAt.toLocal().toString().split('.').first),
                            if (record.synthesizedAnswer != null)
                              Padding(
                                padding: const EdgeInsets.only(top: 4),
                                child: Text(
                                  record.synthesizedAnswer!,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                          ],
                        ),
                        isThreeLine: record.synthesizedAnswer != null,
                        trailing: IconButton(
                          tooltip: 'Delete',
                          icon: const Icon(Icons.delete_outline_rounded),
                          onPressed: () => _delete(record),
                        ),
                        onTap: () => Navigator.pop(context, record.question),
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

class _EvidencePacketView extends StatelessWidget {
  const _EvidencePacketView({required this.packet});

  final SirisHydroEvidencePacket packet;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  packet.sufficientEvidence
                      ? Icons.verified_rounded
                      : Icons.warning_amber_rounded,
                  color: packet.sufficientEvidence
                      ? scheme.primary
                      : scheme.error,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        packet.sufficientEvidence
                            ? 'Source evidence found'
                            : 'Insufficient source evidence',
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 4),
                      Text(packet.guidance),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        if (packet.synthesizedAnswer != null) ...[
          const SizedBox(height: 12),
          Card(
            color: scheme.primaryContainer,
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.auto_awesome_rounded, color: scheme.onPrimaryContainer, size: 18),
                      const SizedBox(width: 8),
                      Text(
                        'Synthesized answer',
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: scheme.onPrimaryContainer,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    packet.synthesizedAnswer!,
                    style: TextStyle(color: scheme.onPrimaryContainer),
                  ),
                ],
              ),
            ),
          ),
        ],
        const SizedBox(height: 12),
        if (packet.evidence.isEmpty)
          const Card(
            child: Padding(
              padding: EdgeInsets.all(18),
              child: Text(
                'No indexed pages matched this question. Add or index the relevant standard before relying on a standards-based answer.',
              ),
            ),
          )
        else ...[
          Row(
            children: [
              Expanded(
                child: Text(
                  'Retrieved evidence',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              OutlinedButton.icon(
                onPressed: () async {
                  await Clipboard.setData(
                    ClipboardData(text: packet.contextText),
                  );
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Evidence context copied.')),
                    );
                  }
                },
                icon: const Icon(Icons.copy_all_rounded),
                label: const Text('Copy context'),
              ),
            ],
          ),
          const SizedBox(height: 10),
          for (final item in packet.evidence)
            Card(
              margin: const EdgeInsets.only(bottom: 12),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.citation,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 6),
                    Text(item.excerpt),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        Chip(label: Text('Page ${item.page}')),
                        Chip(label: Text('Score ${item.score}')),
                        OutlinedButton.icon(
                          onPressed: () async {
                            await Clipboard.setData(
                              ClipboardData(text: item.citation),
                            );
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Citation copied.')),
                              );
                            }
                          },
                          icon: const Icon(Icons.copy_rounded),
                          label: const Text('Copy citation'),
                        ),
                        OutlinedButton.icon(
                          onPressed: () => showStandardPageDialog(
                            context,
                            service: EngineeringStandardsService(),
                            documentId: item.documentId,
                            page: item.page,
                          ),
                          icon: const Icon(Icons.description_outlined),
                          label: const Text('View source page'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
        ],
      ],
    );
  }
}
