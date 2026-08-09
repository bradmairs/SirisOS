import 'package:flutter/material.dart';

import '../core/siris_context_service.dart';
import '../services/project_service.dart';

class CurrentProjectScreen extends StatefulWidget {
  const CurrentProjectScreen({super.key});

  @override
  State<CurrentProjectScreen> createState() => _CurrentProjectScreenState();
}

class _CurrentProjectScreenState extends State<CurrentProjectScreen> {
  final _service = ProjectService();
  late Future<_CurrentProjectData> _data;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _data = _load();
  }

  Future<_CurrentProjectData> _load() async {
    final values = await Future.wait([
      _service.currentProject(),
      _service.listProjects(),
    ]);
    return _CurrentProjectData(
      current: values[0] as CurrentProjectState,
      projects: values[1] as List<ProjectRecord>,
    );
  }

  void _refresh() => setState(() {
        _data = _load();
      });

  Future<void> _select(String? projectId) async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await _service.setCurrentProject(projectId);
      await SirisCoreContextService.instance.refresh();
      if (!mounted) return;
      setState(() {
        _saving = false;
        _data = _load();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to change current project: $error')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: FutureBuilder<_CurrentProjectData>(
        future: _data,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.error_outline_rounded, size: 46),
                    const SizedBox(height: 12),
                    Text('Current project unavailable', style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 8),
                    Text('${snapshot.error}', textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    FilledButton.tonalIcon(
                      onPressed: _refresh,
                      icon: const Icon(Icons.refresh_rounded),
                      label: const Text('Try again'),
                    ),
                  ],
                ),
              ),
            );
          }

          final data = snapshot.requireData;
          final current = data.current.project;
          final selectable = data.projects
              .where((project) => project.status == 'active' || project.status == 'paused')
              .toList(growable: false);

          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
            children: [
              Text('Current project', style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 6),
              Text(
                'An explicit project context for Mission Control, briefings and future SirisAI workflows. SirisOS never guesses this selection.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 20),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: current == null
                      ? Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Icon(Icons.radio_button_unchecked_rounded),
                                const SizedBox(width: 10),
                                Text('No current project', style: Theme.of(context).textTheme.titleMedium),
                              ],
                            ),
                            const SizedBox(height: 8),
                            const Text('Select one below when you want SirisOS to carry project context across modules.'),
                          ],
                        )
                      : Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Icon(Icons.adjust_rounded),
                                const SizedBox(width: 10),
                                Expanded(child: Text(current.name, style: Theme.of(context).textTheme.titleLarge)),
                                if (_saving)
                                  const SizedBox.square(
                                    dimension: 20,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Text('${_kindLabel(current.kind)} · ${_statusLabel(current.status)}'),
                            if (current.description.isNotEmpty) ...[
                              const SizedBox(height: 8),
                              Text(current.description),
                            ],
                            const SizedBox(height: 14),
                            OutlinedButton.icon(
                              onPressed: _saving ? null : () => _select(null),
                              icon: const Icon(Icons.close_rounded),
                              label: const Text('Clear current project'),
                            ),
                          ],
                        ),
                ),
              ),
              const SizedBox(height: 22),
              Text('Available projects', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 10),
              if (selectable.isEmpty)
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(18),
                    child: Text('Create an active or paused project first.'),
                  ),
                )
              else
                for (final project in selectable)
                  Card(
                    child: RadioListTile<String>(
                      value: project.id,
                      groupValue: current?.id,
                      onChanged: _saving ? null : _select,
                      title: Text(project.name),
                      subtitle: Text('${_kindLabel(project.kind)} · ${_statusLabel(project.status)}'),
                      secondary: Icon(_kindIcon(project.kind)),
                    ),
                  ),
            ],
          );
        },
      ),
    );
  }
}

class _CurrentProjectData {
  const _CurrentProjectData({required this.current, required this.projects});
  final CurrentProjectState current;
  final List<ProjectRecord> projects;
}

String _kindLabel(String kind) => switch (kind) {
      'engineering' => 'Engineering',
      'homelab' => 'Homelab',
      'travel' => 'Travel',
      'fitness' => 'Fitness',
      'personal' => 'Personal',
      _ => 'Other',
    };

String _statusLabel(String status) => switch (status) {
      'active' => 'Active',
      'paused' => 'Paused',
      'completed' => 'Completed',
      'archived' => 'Archived',
      _ => status,
    };

IconData _kindIcon(String kind) => switch (kind) {
      'engineering' => Icons.engineering_rounded,
      'homelab' => Icons.dns_rounded,
      'travel' => Icons.flight_takeoff_rounded,
      'fitness' => Icons.fitness_center_rounded,
      'personal' => Icons.person_rounded,
      _ => Icons.folder_rounded,
    };
