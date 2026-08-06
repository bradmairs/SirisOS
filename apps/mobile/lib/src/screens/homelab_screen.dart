import 'package:flutter/material.dart';

import '../models/docker_summary.dart';
import '../services/homelab_service.dart';
import 'container_detail_screen.dart';

class HomelabScreen extends StatefulWidget {
  const HomelabScreen({super.key});

  @override
  State<HomelabScreen> createState() => _HomelabScreenState();
}

class _HomelabScreenState extends State<HomelabScreen> {
  final HomelabService _service = HomelabService();
  late Future<DockerSummary> _summaryFuture;

  @override
  void initState() {
    super.initState();
    _summaryFuture = _service.fetchDockerSummary();
  }

  Future<void> _refresh() async {
    final next = _service.fetchDockerSummary();
    setState(() => _summaryFuture = next);
    await next;
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: FutureBuilder<DockerSummary>(
        future: _summaryFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError || !snapshot.hasData) {
            return _HomelabErrorState(onRetry: _refresh);
          }

          final summary = snapshot.data!;
          return RefreshIndicator(
            onRefresh: _refresh,
            child: CustomScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              slivers: [
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
                  sliver: SliverToBoxAdapter(
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Homelab',
                                style: Theme.of(context).textTheme.headlineMedium,
                              ),
                              const SizedBox(height: 6),
                              Text(
                                summary.available
                                    ? 'Live Docker health and resource usage.'
                                    : 'Docker monitoring is currently unavailable.',
                                style: TextStyle(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                        ),
                        IconButton.filledTonal(
                          onPressed: _refresh,
                          tooltip: 'Refresh Homelab',
                          icon: const Icon(Icons.refresh_rounded),
                        ),
                      ],
                    ),
                  ),
                ),
                SliverPadding(
                  padding: const EdgeInsets.all(20),
                  sliver: SliverToBoxAdapter(
                    child: _SummaryPanel(summary: summary),
                  ),
                ),
                if (!summary.available)
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
                    sliver: SliverToBoxAdapter(
                      child: _UnavailablePanel(error: summary.error),
                    ),
                  )
                else if (summary.containers.isEmpty)
                  const SliverFillRemaining(
                    hasScrollBody: false,
                    child: Center(child: Text('No Docker containers found.')),
                  )
                else
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
                    sliver: SliverList.separated(
                      itemCount: summary.containers.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        return _ContainerCard(
                          container: summary.containers[index],
                        );
                      },
                    ),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _SummaryPanel extends StatelessWidget {
  const _SummaryPanel({required this.summary});

  final DockerSummary summary;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Wrap(
          spacing: 28,
          runSpacing: 18,
          children: [
            _Metric(label: 'Total', value: '${summary.total}'),
            _Metric(label: 'Running', value: '${summary.running}'),
            _Metric(label: 'Stopped', value: '${summary.stopped}'),
            _Metric(label: 'Unhealthy', value: '${summary.unhealthy}'),
          ],
        ),
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 110,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(value, style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 4),
          Text(
            label,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

class _ContainerCard extends StatelessWidget {
  const _ContainerCard({required this.container});

  final DockerContainerInfo container;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final statusColor = container.isUnhealthy
        ? scheme.error
        : container.isRunning
            ? scheme.primary
            : scheme.onSurfaceVariant;

    final statusLabel = container.isUnhealthy
        ? 'Unhealthy'
        : container.isRunning
            ? (container.health == 'healthy' ? 'Healthy' : 'Running')
            : container.state;

    return GestureDetector(
      onTap: () {
        Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => ContainerDetailScreen(
              initialContainer: container,
            ),
          ),
        );
      },
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    backgroundColor: statusColor.withValues(alpha: 0.14),
                    child: Icon(Icons.inventory_2_rounded, color: statusColor),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          container.name,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 3),
                        Text(
                          container.image,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(color: scheme.onSurfaceVariant),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.14),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      statusLabel,
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  const SizedBox(width: 4),
                  Icon(
                    Icons.chevron_right_rounded,
                    color: scheme.onSurfaceVariant,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              if (container.isRunning)
                Row(
                  children: [
                    Expanded(
                      child: _ResourceMetric(
                        icon: Icons.speed_rounded,
                        label: 'CPU',
                        value: container.cpuPercent == null
                            ? '—'
                            : '${container.cpuPercent!.toStringAsFixed(1)}%',
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _ResourceMetric(
                        icon: Icons.memory_rounded,
                        label: 'Memory',
                        value: container.memoryUsageLabel,
                        detail: container.memoryPercent == null
                            ? null
                            : '${container.memoryPercent!.toStringAsFixed(1)}%',
                      ),
                    ),
                  ],
                )
              else
                Text(
                  container.status,
                  style: TextStyle(color: scheme.onSurfaceVariant),
                ),
              const SizedBox(height: 12),
              Text(
                'ID ${container.containerId}',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ResourceMetric extends StatelessWidget {
  const _ResourceMetric({
    required this.icon,
    required this.label,
    required this.value,
    this.detail,
  });

  final IconData icon;
  final String label;
  final String value;
  final String? detail;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.45),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Icon(icon, size: 20, color: scheme.primary),
          const SizedBox(width: 9),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                ),
                Text(
                  detail == null ? value : '$value · $detail',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _UnavailablePanel extends StatelessWidget {
  const _UnavailablePanel({required this.error});

  final String? error;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              Icons.cloud_off_rounded,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Docker unavailable',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 6),
                  Text(error ?? 'The Docker socket proxy could not be reached.'),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HomelabErrorState extends StatelessWidget {
  const _HomelabErrorState({required this.onRetry});

  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.dns_outlined, size: 52),
            const SizedBox(height: 16),
            Text(
              'Could not load Homelab',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}
