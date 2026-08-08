import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../services/knowledge_service.dart';

class KnowledgeRelationshipsPanel extends StatefulWidget {
  const KnowledgeRelationshipsPanel({
    required this.notePath,
    required this.onOpen,
    super.key,
  });

  final String notePath;
  final Future<void> Function(KnowledgeNoteSummary note) onOpen;

  @override
  State<KnowledgeRelationshipsPanel> createState() => _KnowledgeRelationshipsPanelState();
}

class _KnowledgeRelationshipsPanelState extends State<KnowledgeRelationshipsPanel> {
  final _service = KnowledgeService();
  late Future<List<KnowledgeRelatedNote>> _related;
  late Future<KnowledgeGraph> _graph;

  @override
  void initState() {
    super.initState();
    _related = _service.related(widget.notePath);
    _graph = _service.graph(widget.notePath);
  }

  Future<void> _showGraph() async {
    await showDialog<void>(
      context: context,
      builder: (context) => Dialog(
        child: SizedBox(
          width: 760,
          height: 620,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: FutureBuilder<KnowledgeGraph>(
              future: _graph,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Center(child: Text('Graph unavailable: ${snapshot.error}'));
                }
                final graph = snapshot.requireData;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(child: Text('Local Knowledge Graph', style: Theme.of(context).textTheme.headlineSmall)),
                        IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close_rounded)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text('Deterministic relationships around ${graph.centerPath}', style: Theme.of(context).textTheme.bodySmall),
                    const SizedBox(height: 16),
                    Expanded(
                      child: graph.nodes.length <= 1
                          ? const Center(child: Text('No related notes yet.'))
                          : CustomPaint(
                              painter: _KnowledgeGraphPainter(graph: graph, theme: Theme.of(context)),
                              child: const SizedBox.expand(),
                            ),
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: const [
                        _Legend(label: 'link', icon: Icons.arrow_outward_rounded),
                        _Legend(label: 'backlink', icon: Icons.subdirectory_arrow_left_rounded),
                        _Legend(label: 'shared tag', icon: Icons.tag_rounded),
                        _Legend(label: 'same folder', icon: Icons.folder_outlined),
                      ],
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<KnowledgeRelatedNote>>(
      future: _related,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const LinearProgressIndicator();
        }
        if (snapshot.hasError) {
          return Text('Related notes unavailable: ${snapshot.error}', style: Theme.of(context).textTheme.bodySmall);
        }
        final related = snapshot.data ?? const [];
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text('Related notes · ${related.length}', style: Theme.of(context).textTheme.titleSmall)),
                TextButton.icon(
                  onPressed: _showGraph,
                  icon: const Icon(Icons.hub_rounded, size: 18),
                  label: const Text('Graph'),
                ),
              ],
            ),
            if (related.isEmpty)
              Text('No deterministic relationships found.', style: Theme.of(context).textTheme.bodySmall)
            else
              SizedBox(
                height: 48,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: related.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 6),
                  itemBuilder: (_, index) {
                    final item = related[index];
                    return ActionChip(
                      avatar: const Icon(Icons.account_tree_outlined, size: 16),
                      label: Text(item.note.title),
                      tooltip: item.reasons.join(' · '),
                      onPressed: () => widget.onOpen(item.note),
                    );
                  },
                ),
              ),
          ],
        );
      },
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend({required this.label, required this.icon});
  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Chip(
        avatar: Icon(icon, size: 15),
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
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) * 0.36;
    final positions = <String, Offset>{graph.centerPath: center};
    final neighbors = graph.nodes.where((node) => !node.center).toList(growable: false);

    for (var i = 0; i < neighbors.length; i++) {
      final angle = (math.pi * 2 * i / neighbors.length) - math.pi / 2;
      positions[neighbors[i].id] = Offset(center.dx + radius * math.cos(angle), center.dy + radius * math.sin(angle));
    }

    final edgePaint = Paint()
      ..color = theme.colorScheme.outlineVariant
      ..strokeWidth = 1.5;
    for (final edge in graph.edges) {
      final start = positions[edge.source];
      final end = positions[edge.target];
      if (start != null && end != null) canvas.drawLine(start, end, edgePaint);
    }

    for (final node in graph.nodes) {
      final point = positions[node.id];
      if (point == null) continue;
      final nodePaint = Paint()
        ..color = node.center ? theme.colorScheme.primaryContainer : theme.colorScheme.surfaceContainerHighest;
      canvas.drawCircle(point, node.center ? 34 : 26, nodePaint);
      final textPainter = TextPainter(
        text: TextSpan(
          text: _shortLabel(node.title),
          style: theme.textTheme.labelSmall?.copyWith(
            color: node.center ? theme.colorScheme.onPrimaryContainer : theme.colorScheme.onSurfaceVariant,
            fontWeight: node.center ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
        textAlign: TextAlign.center,
        maxLines: 2,
        textDirection: TextDirection.ltr,
        ellipsis: '…',
      )..layout(maxWidth: node.center ? 90 : 76);
      textPainter.paint(canvas, point - Offset(textPainter.width / 2, textPainter.height / 2));
    }
  }

  String _shortLabel(String value) => value.length <= 28 ? value : '${value.substring(0, 25)}…';

  @override
  bool shouldRepaint(covariant _KnowledgeGraphPainter oldDelegate) => oldDelegate.graph != graph || oldDelegate.theme != theme;
}
