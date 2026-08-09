import 'dart:async';

import 'package:flutter/material.dart';

import '../models/home_assistant_snapshot.dart';
import '../services/home_assistant_service.dart';
import '../widgets/siris_design_system.dart';

class HomeAssistantScreen extends StatefulWidget {
  const HomeAssistantScreen({super.key});

  static const routeName = '/home-assistant';

  @override
  State<HomeAssistantScreen> createState() => _HomeAssistantScreenState();
}

class _HomeAssistantScreenState extends State<HomeAssistantScreen> {
  final HomeAssistantService _service = HomeAssistantService();
  final TextEditingController _searchController = TextEditingController();
  late Future<HomeAssistantSnapshot> _snapshotFuture;
  Timer? _refreshTimer;
  String _domain = 'all';
  bool _actionRunning = false;

  @override
  void initState() {
    super.initState();
    _snapshotFuture = _service.fetchSnapshot();
    _refreshTimer = Timer.periodic(
      const Duration(seconds: 2),
      (_) => _refresh(showLoading: false),
    );
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _refresh({bool showLoading = true}) async {
    if (!mounted) return;
    final next = _service.fetchSnapshot();
    if (showLoading) {
      setState(() {
        _snapshotFuture = next;
      });
    } else {
      try {
        final snapshot = await next;
        if (mounted) {
          setState(() {
            _snapshotFuture = Future.value(snapshot);
          });
        }
      } catch (_) {
        // Keep the last useful snapshot during transient integration failures.
      }
    }
  }

  Future<void> _call(
    HomeAssistantEntity entity,
    String service,
  ) async {
    if (_actionRunning) return;
    setState(() => _actionRunning = true);
    try {
      await _service.callService(
        domain: entity.domain,
        service: service,
        entityId: entity.entityId,
      );
      await Future<void>.delayed(const Duration(milliseconds: 350));
      await _refresh(showLoading: false);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Home Assistant action failed: $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _actionRunning = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Home Assistant'),
        actions: [
          IconButton(
            onPressed: () => _refresh(),
            tooltip: 'Refresh Home Assistant',
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: FutureBuilder<HomeAssistantSnapshot>(
        future: _snapshotFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError || !snapshot.hasData) {
            return _ErrorState(onRetry: () => _refresh());
          }

          final data = snapshot.data!;
          if (!data.configured) {
            return const _MessageState(
              icon: Icons.home_work_outlined,
              title: 'Home Assistant is not configured',
              message:
                  'Set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN on the SirisOS backend.',
            );
          }
          if (!data.available) {
            return _MessageState(
              icon: Icons.cloud_off_rounded,
              title: 'Home Assistant is unavailable',
              message: data.error ?? 'SirisOS could not read Home Assistant state.',
            );
          }

          final domains = <String>{
            'all',
            ...data.entities.map((entity) => entity.domain),
          }.toList(growable: false)
            ..sort();
          final query = _searchController.text.trim().toLowerCase();
          final entities = data.entities.where((entity) {
            if (_domain != 'all' && entity.domain != _domain) return false;
            if (query.isEmpty) return true;
            return entity.name.toLowerCase().contains(query) ||
                entity.entityId.toLowerCase().contains(query) ||
                entity.state.toLowerCase().contains(query);
          }).toList(growable: false);

          return RefreshIndicator(
            onRefresh: () => _refresh(),
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
              children: [
                SirisPanel(
                  title: 'Live Home State',
                  child: Wrap(
                    spacing: 20,
                    runSpacing: 14,
                    children: [
                      SirisMetric(label: 'Entities', value: '${data.total}'),
                      SirisMetric(
                        label: 'Unavailable',
                        value: '${data.unavailable}',
                      ),
                      SirisStatusChip(
                        label: data.unavailable == 0
                            ? 'Healthy'
                            : '${data.unavailable} need attention',
                        status: data.unavailable == 0
                            ? SirisStatus.success
                            : SirisStatus.warning,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 18),
                TextField(
                  controller: _searchController,
                  onChanged: (_) => setState(() {}),
                  decoration: const InputDecoration(
                    prefixIcon: Icon(Icons.search_rounded),
                    hintText: 'Search entities, IDs or states',
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  height: 42,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: domains.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 8),
                    itemBuilder: (context, index) {
                      final domain = domains[index];
                      return ChoiceChip(
                        label: Text(domain == 'all' ? 'All' : domain),
                        selected: _domain == domain,
                        onSelected: (_) => setState(() => _domain = domain),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 18),
                if (entities.isEmpty)
                  const _MessageState(
                    icon: Icons.search_off_rounded,
                    title: 'No matching entities',
                    message: 'Try another search term or domain filter.',
                  )
                else
                  ...entities.map(
                    (entity) => Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: _EntityCard(
                        entity: entity,
                        busy: _actionRunning,
                        onAction: (service) => _call(entity, service),
                      ),
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

class _EntityCard extends StatelessWidget {
  const _EntityCard({
    required this.entity,
    required this.busy,
    required this.onAction,
  });

  final HomeAssistantEntity entity;
  final bool busy;
  final ValueChanged<String> onAction;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final unavailable = entity.state == 'unavailable' || entity.state == 'unknown';
    return SirisCard(
      child: Row(
        children: [
          CircleAvatar(
            backgroundColor: (unavailable ? scheme.error : scheme.primary)
                .withValues(alpha: 0.12),
            child: Icon(
              _domainIcon(entity.domain),
              color: unavailable ? scheme.error : scheme.primary,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(entity.name, style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 3),
                Text(
                  entity.entityId,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          SirisStatusChip(
            label: entity.state,
            status: unavailable ? SirisStatus.warning : SirisStatus.info,
          ),
          const SizedBox(width: 10),
          ..._actions(entity).map(
            (action) => Padding(
              padding: const EdgeInsets.only(left: 6),
              child: IconButton.filledTonal(
                onPressed: busy ? null : () => onAction(action.service),
                tooltip: action.label,
                icon: Icon(action.icon),
              ),
            ),
          ),
        ],
      ),
    );
  }

  static IconData _domainIcon(String domain) => switch (domain) {
        'light' => Icons.lightbulb_rounded,
        'switch' => Icons.toggle_on_rounded,
        'input_boolean' => Icons.check_circle_outline_rounded,
        'cover' => Icons.blinds_rounded,
        'sensor' => Icons.sensors_rounded,
        'binary_sensor' => Icons.motion_photos_on_rounded,
        'climate' => Icons.thermostat_rounded,
        'media_player' => Icons.speaker_rounded,
        _ => Icons.home_rounded,
      };

  static List<_EntityAction> _actions(HomeAssistantEntity entity) {
    switch (entity.domain) {
      case 'light':
      case 'switch':
      case 'input_boolean':
        return [
          _EntityAction(
            service: entity.state == 'on' ? 'turn_off' : 'turn_on',
            label: entity.state == 'on' ? 'Turn off' : 'Turn on',
            icon: entity.state == 'on'
                ? Icons.power_settings_new_rounded
                : Icons.power_rounded,
          ),
        ];
      case 'cover':
        return const [
          _EntityAction(
            service: 'open_cover',
            label: 'Open',
            icon: Icons.keyboard_arrow_up_rounded,
          ),
          _EntityAction(
            service: 'close_cover',
            label: 'Close',
            icon: Icons.keyboard_arrow_down_rounded,
          ),
        ];
      default:
        return const [];
    }
  }
}

class _EntityAction {
  const _EntityAction({
    required this.service,
    required this.label,
    required this.icon,
  });

  final String service;
  final String label;
  final IconData icon;
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.onRetry});

  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: FilledButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh_rounded),
          label: const Text('Retry Home Assistant'),
        ),
      );
}

class _MessageState extends StatelessWidget {
  const _MessageState({
    required this.icon,
    required this.title,
    required this.message,
  });

  final IconData icon;
  final String title;
  final String message;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 36),
        child: Column(
          children: [
            Icon(icon, size: 48),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 7),
            Text(message, textAlign: TextAlign.center),
          ],
        ),
      );
}
