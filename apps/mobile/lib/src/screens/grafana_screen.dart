import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/grafana_snapshot.dart';
import '../services/grafana_service.dart';
import '../widgets/siris_design_system.dart';

class GrafanaScreen extends StatefulWidget {
  const GrafanaScreen({super.key});

  static const routeName = '/grafana';

  @override
  State<GrafanaScreen> createState() => _GrafanaScreenState();
}

class _GrafanaScreenState extends State<GrafanaScreen> {
  final GrafanaService _service = GrafanaService();
  final TextEditingController _searchController = TextEditingController();
  late Future<GrafanaSnapshot> _future;
  String _query = '';

  @override
  void initState() {
    super.initState();
    _future = _service.fetchSnapshot();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    final next = _service.fetchSnapshot();
    setState(() {
      _future = next;
    });
    await next;
  }

  Future<void> _openDashboard(GrafanaDashboardInfo dashboard) async {
    final uri = Uri.tryParse(dashboard.url);
    if (uri == null || !await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open Grafana dashboard.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('Grafana'),
          actions: [
            IconButton(
              onPressed: _refresh,
              tooltip: 'Refresh',
              icon: const Icon(Icons.refresh_rounded),
            ),
          ],
        ),
        body: SafeArea(
          child: FutureBuilder<GrafanaSnapshot>(
            future: _future,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError || !snapshot.hasData) {
                return Center(
                  child: FilledButton.icon(
                    onPressed: _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                    label: const Text('Retry Grafana'),
                  ),
                );
              }

              final data = snapshot.data!;
              if (!data.configured) {
                return const Center(
                  child: Padding(
                    padding: EdgeInsets.all(32),
                    child: Text('Grafana is not configured in SirisOS.'),
                  ),
                );
              }
              if (!data.available) {
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Text(data.error ?? 'Grafana is unavailable.'),
                  ),
                );
              }

              final query = _query.trim().toLowerCase();
              final dashboards = data.dashboards.where((item) {
                if (query.isEmpty) return true;
                return item.title.toLowerCase().contains(query) ||
                    (item.folderTitle?.toLowerCase().contains(query) ?? false) ||
                    item.tags.any((tag) => tag.toLowerCase().contains(query));
              }).toList(growable: false);

              return RefreshIndicator(
                onRefresh: _refresh,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
                  children: [
                    SirisPanel(
                      title: 'Grafana status',
                      subtitle: data.version == null ? 'Connected' : 'Grafana ${data.version}',
                      icon: Icons.analytics_rounded,
                      child: Wrap(
                        spacing: 28,
                        runSpacing: 18,
                        children: [
                          SirisMetric(
                            label: 'Dashboards',
                            value: '${data.dashboardCount}',
                            icon: Icons.dashboard_rounded,
                          ),
                          SirisMetric(
                            label: 'Rendering',
                            value: data.renderingEnabled ? 'Enabled' : 'Optional',
                            icon: Icons.image_rounded,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),
                    TextField(
                      controller: _searchController,
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.search_rounded),
                        hintText: 'Search dashboards, folders or tags',
                      ),
                      onChanged: (value) => setState(() => _query = value),
                    ),
                    const SizedBox(height: 18),
                    if (dashboards.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 40),
                        child: Center(child: Text('No Grafana dashboards found.')),
                      )
                    else
                      ...dashboards.map(
                        (dashboard) => Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: SirisCard(
                            child: Row(
                              children: [
                                const Icon(Icons.dashboard_customize_rounded),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        dashboard.title,
                                        style: Theme.of(context).textTheme.titleMedium,
                                      ),
                                      if (dashboard.folderTitle != null)
                                        Text(
                                          dashboard.folderTitle!,
                                          style: Theme.of(context).textTheme.bodySmall,
                                        ),
                                    ],
                                  ),
                                ),
                                FilledButton.tonalIcon(
                                  onPressed: () => _openDashboard(dashboard),
                                  icon: const Icon(Icons.open_in_new_rounded),
                                  label: const Text('Open'),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              );
            },
          ),
        ),
      );
}
