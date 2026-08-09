import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../services/project_service.dart';

class ProjectContextGraphScreen extends StatefulWidget {
  const ProjectContextGraphScreen({super.key});

  @override
  State<ProjectContextGraphScreen> createState() => _ProjectContextGraphScreenState();
}

class _ProjectContextGraphScreenState extends State<ProjectContextGraphScreen> {
  final _service = ProjectService();
  late Future<_ProjectGraphData> _data;

  @override
  void initState() {
    super.initState();
    _data = _load();
  }

  Future<_ProjectGraphData> _load() async {
    final current = await _service.currentProject();
    final project = current.project;
    if (project == null) return _ProjectGraphData(current: current);
    final graph = await _service.graph(project.id);
    return _ProjectGraphData(current: current, graph: graph);
  }

  void _refresh() => setState(() => _data = _load());

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: FutureBuilder<_ProjectGraphData>(
        future: _data,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _MessageState(
              icon: Icons.hub_outlined,
              title: 'Context graph unavailable',
              message: '${snapshot.error}',
              actionLabel: 'Try again',
              onAction: _refresh,
            );
          }

          final data = snapshot.requireData;
          final project = data.current.project;
          final graph = data.graph;
          if (project == null || graph == null) {
            return const _MessageState(
              icon: Icons.account_tree_outlined,
              title: 'No current project',
              message: 'Choose a current project first. Its explicit relationships will appear here.',
            );
          }

          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Project context graph', style: Theme.of(context).textTheme.headlineMedium),
                        const SizedBox(height: 4),
                        Text(
                          project.name,
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                color: Theme.of(context).colorScheme.primary,
                              ),
                        ),
                      ],
                    ),
                  ),
                  IconButton.filledTonal(
                    tooltip: 'Refresh graph',
                    onPressed: _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                'Only explicit, provenance-backed relationships are shown. SirisOS does not infer project membership.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 18),
              Card(
                child: SizedBox(
                  height: 420,
                  child: graph.nodes.length <= 1
                      ? const Center(
                          child: Padding(
                            padding: EdgeInsets.all(24),
                            child: Text(
                              'This project has no attached Knowledge notes yet. Attach notes from the Projects tab to grow the graph.',
                              textAlign: TextAlign.center,
                            ),
                          ),
                        )
                      : Padding(
                          padding: const EdgeInsets.all(18),
                          child: CustomPaint(
                            painter: _ProjectGraphPainter(
                              graph: graph,
                              theme: Theme.of(context),
                            ),
                            child: const SizedBox.expand(),
                          ),
                        ),
                ),
              ),
              const SizedBox(height: 14),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: const [
                  _LegendChip(icon: Icons.folder_rounded, label: 'Project'),
                  _LegendChip(icon: Icons.menu_book_rounded, label: 'Knowledge note'),
                  _LegendChip(icon: Icons.inventory_2_outlined, label: 'Part of project'),
                  _LegendChip(icon: Icons.link_rounded, label: 'Reference'),
                ],
              ),
              const SizedBox(height: 22),
              Text('Relationships · ${graph.edges.length}', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 10),
              if (graph.edges.isEmpty)
                Text(
                  'No explicit relationships yet.',
                  style: Theme.of(context).textTheme.bodyMedium,
                )
              else
                for (final edge in graph.edges)
                  Card(
                    child: ListTile(
                      leading: Icon(edge.kind == 'contains' ? Icons.inventory_2_outlined : Icons.link_rounded),
                      title: Text(_targetLabel(graph, edge.target)),
                      subtitle: Text('${edge.label} · ${edge.provenance}'),
                    ),
                  ),
            ],
          );
        },
      ),
    );
  }

  String _targetLabel(ProjectGraph graph, String targetId) {
    for (final node in graph.nodes) {
      if (node.id == targetId) return node.label;
    }
    return targetId;
  }
}

class _ProjectGraphData {
  const _ProjectGraphData({required this.current, this.graph});
  final CurrentProjectState current;
  final ProjectGraph? graph;
}

class _MessageState extends StatelessWidget {
  const _MessageState({
    required this.icon,
    required this.title,
    required this.message,
    this.actionLabel,
    this.onAction,
  });

  final IconData icon;
  final String title;
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 52),
            const SizedBox(height: 14),
            Text(title, style: Theme.of(context).textTheme.titleLarge, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 16),
              FilledButton.tonal(onPressed: onAction, child: Text(actionLabel!)),
            ],
          ],
        ),
      ),
    );
  }
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

class _ProjectGraphPainter extends CustomPainter {
  _ProjectGraphPainter({required this.graph, required this.theme});

  final ProjectGraph graph;
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
        ..strokeWidth = edge.kind == 'contains' ? 2.2 : 1.4;
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
          text: _short(node.label),
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
  bool shouldRepaint(covariant _ProjectGraphPainter oldDelegate) =>
      oldDelegate.graph != graph || oldDelegate.theme != theme;
}
