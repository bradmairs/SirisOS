import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../services/knowledge_service.dart';

class KnowledgeGraphScreen extends StatefulWidget {
  const KnowledgeGraphScreen({super.key, required this.centerPath, required this.onOpenNote});

  final String centerPath;
  final Future<void> Function(KnowledgeNoteSummary note) onOpenNote;

  @override
  State<KnowledgeGraphScreen> createState() => _KnowledgeGraphScreenState();
}

class _KnowledgeGraphScreenState extends State<KnowledgeGraphScreen> {
  final _service = KnowledgeService();
  late Future<KnowledgeGraph> _graph;

  @override
  void initState() {
    super.initState();
    _graph = _service.graph(widget.centerPath);
  }

  void _refresh() => setState(() => _graph = _service.graph(widget.centerPath));

  Future<void> _openTarget(KnowledgeGraphNode node) async {
    Navigator.pop(context);
    await Future<void>.delayed(Duration.zero);
    await widget.onOpenNote(KnowledgeNoteSummary(
      path: node.id,
      title: node.title,
      modifiedAt: DateTime.now(),
      sizeBytes: 0,
      tags: const [],
      wikilinks: const [],
      isDailyNote: false,
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      child: SizedBox(
        width: 760,
        height: 680,
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: FutureBuilder<KnowledgeGraph>(
            future: _graph,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return _GraphMessage(
                  icon: Icons.hub_outlined,
                  title: 'Graph unavailable',
                  message: '${snapshot.error}',
                  onRetry: _refresh,
                );
              }
              final graph = snapshot.requireData;
              final centerNode = graph.nodes.firstWhere(
                (node) => node.center,
                orElse: () => graph.nodes.first,
              );
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Knowledge Graph', style: Theme.of(context).textTheme.headlineSmall),
                            const SizedBox(height: 4),
                            Text(
                              centerNode.title,
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                    color: Theme.of(context).colorScheme.primary,
                                  ),
                            ),
                          ],
                        ),
                      ),
                      IconButton(tooltip: 'Refresh', onPressed: _refresh, icon: const Icon(Icons.refresh_rounded)),
                      IconButton(tooltip: 'Close', onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close_rounded)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Deterministic local graph: outgoing links, backlinks, shared tags and folder proximity. No inferred or AI-generated relationships.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: 14),
                  Expanded(
                    flex: 3,
                    child: Card(
                      child: graph.nodes.length <= 1
                          ? const Center(
                              child: Padding(
                                padding: EdgeInsets.all(24),
                                child: Text(
                                  'No related notes yet. Links, backlinks, shared tags or folder proximity will populate this graph.',
                                  textAlign: TextAlign.center,
                                ),
                              ),
                            )
                          : Padding(
                              padding: const EdgeInsets.all(16),
                              child: CustomPaint(
                                painter: _KnowledgeGraphPainter(graph: graph, theme: Theme.of(context)),
                                child: const SizedBox.expand(),
                              ),
                            ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: const [
                      _LegendChip(icon: Icons.arrow_outward_rounded, label: 'Outgoing link'),
                      _LegendChip(icon: Icons.subdirectory_arrow_left_rounded, label: 'Backlink'),
                      _LegendChip(icon: Icons.sell_outlined, label: 'Shared tag'),
                      _LegendChip(icon: Icons.folder_outlined, label: 'Same folder'),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Expanded(
                    flex: 2,
                    child: graph.edges.isEmpty
                        ? const Center(child: Text('No explicit relationships yet.'))
                        : ListView.separated(
                            itemCount: graph.edges.length,
                            separatorBuilder: (_, __) => const SizedBox(height: 4),
                            itemBuilder: (context, index) {
                              final edge = graph.edges[index];
                              final node = graph.nodes.firstWhere(
                                (item) => item.id == edge.target,
                                orElse: () => KnowledgeGraphNode(id: edge.target, title: edge.target, center: false),
                              );
                              return Card(
                                child: ListTile(
                                  dense: true,
                                  leading: Icon(_edgeIcon(edge.kind)),
                                  title: Text(node.title),
                                  subtitle: Text(edge.label),
                                  trailing: const Icon(Icons.chevron_right_rounded),
                                  onTap: () => _openTarget(node),
                                ),
                              );
                            },
                          ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  IconData _edgeIcon(String kind) {
    switch (kind) {
      case 'outgoing':
        return Icons.arrow_outward_rounded;
      case 'backlink':
        return Icons.subdirectory_arrow_left_rounded;
      case 'tag':
        return Icons.sell_outlined;
      default:
        return Icons.folder_outlined;
    }
  }
}

class _GraphMessage extends StatelessWidget {
  const _GraphMessage({required this.icon, required this.title, required this.message, required this.onRetry});
  final IconData icon;
  final String title;
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh_rounded), label: const Text('Try again')),
          ],
        ),
      );
}

class _LegendChip extends StatelessWidget {
  const _LegendChip({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) => Chip(
        avatar: Icon(icon, size: 16),
        label: Text(label),
        visualDensity: VisualDensity.compact,
      );
}

class _KnowledgeGraphPainter extends CustomPainter {
  _KnowledgeGraphPainter({required this.graph, required this.theme});

  final KnowledgeGraph graph;
  final ThemeData theme;

  @override
  void paint(Canvas canvas, Size size) {
    final centerNode = graph.nodes.firstWhere(
      (node) => node.center,
      orElse: () => graph.nodes.first,
    );
    final neighbors = graph.nodes.where((node) => node.id != centerNode.id).toList(growable: false);
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) * 0.34;
    final positions = <String, Offset>{centerNode.id: center};

    for (var i = 0; i < neighbors.length; i++) {
      final angle = (math.pi * 2 * i / neighbors.length) - math.pi / 2;
      positions[neighbors[i].id] = Offset(
        center.dx + radius * math.cos(angle),
        center.dy + radius * math.sin(angle),
      );
    }

    for (final edge in graph.edges) {
      final start = positions[edge.source];
      final end = positions[edge.target];
      if (start == null || end == null) continue;
      final paint = Paint()
        ..color = theme.colorScheme.outlineVariant
        ..strokeWidth = edge.kind == 'outgoing' || edge.kind == 'backlink' ? 2.0 : 1.2;
      canvas.drawLine(start, end, paint);
    }

    for (final node in graph.nodes) {
      final point = positions[node.id];
      if (point == null) continue;
      final isCenter = node.id == centerNode.id;
      final paint = Paint()
        ..color = isCenter
            ? theme.colorScheme.primaryContainer
            : theme.colorScheme.surfaceContainerHighest;
      canvas.drawCircle(point, isCenter ? 38 : 30, paint);

      final textPainter = TextPainter(
        text: TextSpan(
          text: _short(node.title),
          style: theme.textTheme.labelSmall?.copyWith(
            color: isCenter
                ? theme.colorScheme.onPrimaryContainer
                : theme.colorScheme.onSurfaceVariant,
            fontWeight: isCenter ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
        textAlign: TextAlign.center,
        maxLines: 2,
        textDirection: TextDirection.ltr,
        ellipsis: '…',
      )..layout(maxWidth: isCenter ? 105 : 88);
      textPainter.paint(
        canvas,
        point - Offset(textPainter.width / 2, textPainter.height / 2),
      );
    }
  }

  String _short(String value) => value.length <= 30 ? value : '${value.substring(0, 27)}…';

  @override
  bool shouldRepaint(covariant _KnowledgeGraphPainter oldDelegate) =>
      oldDelegate.graph != graph || oldDelegate.theme != theme;
}
