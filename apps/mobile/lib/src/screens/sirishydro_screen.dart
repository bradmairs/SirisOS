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

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text('SirisHydro', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 4),
          Text(
            'Evidence-first engineering retrieval from your private standards library. AI answer generation comes later.',
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
