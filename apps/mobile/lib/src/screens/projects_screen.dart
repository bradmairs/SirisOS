import 'package:flutter/material.dart';

import '../services/knowledge_service.dart';
import '../services/project_service.dart';

class ProjectsScreen extends StatefulWidget {
  const ProjectsScreen({super.key});

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen> {
  final _service = ProjectService();
  late Future<List<ProjectRecord>> _projects;

  @override
  void initState() {
    super.initState();
    _projects = _service.listProjects();
  }

  void _refresh() => setState(() {
        _projects = _service.listProjects();
      });

  Future<void> _createProject() async {
    final draft = await showDialog<_ProjectDraft>(
      context: context,
      builder: (_) => const _ProjectFormDialog(),
    );
    if (draft == null) return;
    try {
      await _service.createProject(
        name: draft.name,
        description: draft.description,
        kind: draft.kind,
        tags: draft.tags,
      );
      if (!mounted) return;
      _refresh();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Created ${draft.name}.')),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to create project: $error')),
      );
    }
  }

  Future<void> _openProject(ProjectRecord project) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (_) => FractionallySizedBox(
        heightFactor: 0.9,
        child: _ProjectDetailSheet(
          project: project,
          onProjectChanged: _refresh,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: RefreshIndicator(
        onRefresh: () async {
          _refresh();
          await _projects;
        },
        child: FutureBuilder<List<ProjectRecord>>(
          future: _projects,
          builder: (context, snapshot) {
            return ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Projects', style: Theme.of(context).textTheme.headlineMedium),
                          const SizedBox(height: 4),
                          Text(
                            'Context containers for Engineering, Homelab and the rest of SirisOS.',
                            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                                ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    FilledButton.icon(
                      onPressed: _createProject,
                      icon: const Icon(Icons.add_rounded),
                      label: const Text('New project'),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                if (snapshot.connectionState == ConnectionState.waiting)
                  const Padding(
                    padding: EdgeInsets.only(top: 80),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (snapshot.hasError)
                  _StateCard(
                    icon: Icons.error_outline_rounded,
                    title: 'Projects unavailable',
                    message: '${snapshot.error}',
                    actionLabel: 'Try again',
                    onAction: _refresh,
                  )
                else if ((snapshot.data ?? const []).isEmpty)
                  _StateCard(
                    icon: Icons.folder_open_rounded,
                    title: 'No projects yet',
                    message: 'Create a project to group notes and future tasks, calculations, events and files.',
                    actionLabel: 'Create project',
                    onAction: _createProject,
                  )
                else
                  ...snapshot.requireData.map(
                    (project) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: _ProjectCard(
                        project: project,
                        onTap: () => _openProject(project),
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _ProjectCard extends StatelessWidget {
  const _ProjectCard({required this.project, required this.onTap});

  final ProjectRecord project;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                child: Icon(_kindIcon(project.kind)),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(project.name, style: Theme.of(context).textTheme.titleMedium),
                        ),
                        _StatusChip(status: project.status),
                      ],
                    ),
                    if (project.description.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(
                        project.description,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                      ),
                    ],
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        Chip(
                          avatar: Icon(_kindIcon(project.kind), size: 15),
                          label: Text(_kindLabel(project.kind)),
                          visualDensity: VisualDensity.compact,
                        ),
                        for (final tag in project.tags.take(4))
                          Chip(
                            label: Text('#$tag'),
                            visualDensity: VisualDensity.compact,
                          ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Icon(Icons.chevron_right_rounded),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProjectDetailSheet extends StatefulWidget {
  const _ProjectDetailSheet({required this.project, required this.onProjectChanged});

  final ProjectRecord project;
  final VoidCallback onProjectChanged;

  @override
  State<_ProjectDetailSheet> createState() => _ProjectDetailSheetState();
}

class _ProjectDetailSheetState extends State<_ProjectDetailSheet> {
  final _projectService = ProjectService();
  final _knowledgeService = KnowledgeService();
  late ProjectRecord _project;
  late Future<List<ProjectRelationship>> _relationships;
  bool _updatingStatus = false;

  @override
  void initState() {
    super.initState();
    _project = widget.project;
    _relationships = _projectService.relationships(_project.id);
  }

  void _refreshRelationships() => setState(() {
        _relationships = _projectService.relationships(_project.id);
      });

  Future<void> _setStatus(String status) async {
    if (_updatingStatus || status == _project.status) return;
    setState(() => _updatingStatus = true);
    try {
      final updated = await _projectService.updateProject(_project.id, status: status);
      if (!mounted) return;
      setState(() {
        _project = updated;
        _updatingStatus = false;
      });
      widget.onProjectChanged();
    } catch (error) {
      if (!mounted) return;
      setState(() => _updatingStatus = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to update project: $error')),
      );
    }
  }

  Future<void> _attachKnowledge() async {
    final note = await showDialog<KnowledgeNoteSummary>(
      context: context,
      builder: (_) => _KnowledgePickerDialog(service: _knowledgeService),
    );
    if (note == null || !mounted) return;

    final relationshipKind = await showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(
        title: Text('Attach “${note.title}”'),
        children: [
          SimpleDialogOption(
            onPressed: () => Navigator.pop(context, 'contains'),
            child: const ListTile(
              leading: Icon(Icons.inventory_2_outlined),
              title: Text('Part of this project'),
              subtitle: Text('The note belongs to the project context.'),
            ),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(context, 'references'),
            child: const ListTile(
              leading: Icon(Icons.link_rounded),
              title: Text('Reference only'),
              subtitle: Text('The project refers to the note but does not contain it.'),
            ),
          ),
        ],
      ),
    );
    if (relationshipKind == null || !mounted) return;

    try {
      await _projectService.attachKnowledgeNote(
        _project.id,
        note.path,
        kind: relationshipKind,
      );
      if (!mounted) return;
      _refreshRelationships();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to attach note: $error')),
      );
    }
  }

  Future<void> _remove(ProjectRelationship relationship) async {
    try {
      await _projectService.removeRelationship(_project.id, relationship.id);
      if (!mounted) return;
      _refreshRelationships();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to remove relationship: $error')),
      );
    }
  }

  Future<void> _previewNote(ProjectRelationship relationship) async {
    try {
      final note = await _knowledgeService.note(relationship.targetId);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => Dialog(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760, maxHeight: 680),
            child: Padding(
              padding: const EdgeInsets.all(22),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text(note.title, style: Theme.of(context).textTheme.headlineSmall)),
                      IconButton(
                        onPressed: () => Navigator.pop(context),
                        icon: const Icon(Icons.close_rounded),
                      ),
                    ],
                  ),
                  Text(note.path, style: Theme.of(context).textTheme.bodySmall),
                  const Divider(height: 24),
                  Expanded(
                    child: SelectionArea(
                      child: SingleChildScrollView(
                        child: Text(note.content, style: const TextStyle(fontFamily: 'monospace', height: 1.45)),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to open note: $error')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 6, 20, 32),
      children: [
        Row(
          children: [
            CircleAvatar(radius: 24, child: Icon(_kindIcon(_project.kind))),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(_project.name, style: Theme.of(context).textTheme.headlineSmall),
                  Text(_kindLabel(_project.kind), style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
            if (_updatingStatus)
              const SizedBox.square(dimension: 22, child: CircularProgressIndicator(strokeWidth: 2))
            else
              PopupMenuButton<String>(
                tooltip: 'Project status',
                onSelected: _setStatus,
                itemBuilder: (_) => const [
                  PopupMenuItem(value: 'active', child: Text('Active')),
                  PopupMenuItem(value: 'paused', child: Text('Paused')),
                  PopupMenuItem(value: 'completed', child: Text('Completed')),
                  PopupMenuItem(value: 'archived', child: Text('Archived')),
                ],
                child: _StatusChip(status: _project.status),
              ),
          ],
        ),
        if (_project.description.isNotEmpty) ...[
          const SizedBox(height: 16),
          Text(_project.description),
        ],
        if (_project.tags.isNotEmpty) ...[
          const SizedBox(height: 14),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: _project.tags.map((tag) => Chip(label: Text('#$tag'))).toList(growable: false),
          ),
        ],
        const SizedBox(height: 24),
        Row(
          children: [
            Expanded(child: Text('Knowledge', style: Theme.of(context).textTheme.titleLarge)),
            FilledButton.tonalIcon(
              onPressed: _attachKnowledge,
              icon: const Icon(Icons.add_link_rounded),
              label: const Text('Attach note'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        FutureBuilder<List<ProjectRelationship>>(
          future: _relationships,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const LinearProgressIndicator();
            }
            if (snapshot.hasError) {
              return _StateCard(
                icon: Icons.link_off_rounded,
                title: 'Relationships unavailable',
                message: '${snapshot.error}',
                actionLabel: 'Try again',
                onAction: _refreshRelationships,
              );
            }
            final values = snapshot.data ?? const [];
            if (values.isEmpty) {
              return _StateCard(
                icon: Icons.menu_book_outlined,
                title: 'No Knowledge attached',
                message: 'Attach an Obsidian note to make it part of this project context.',
                actionLabel: 'Attach note',
                onAction: _attachKnowledge,
              );
            }
            return Column(
              children: [
                for (final relationship in values)
                  Card(
                    child: ListTile(
                      leading: Icon(
                        relationship.kind == 'contains' ? Icons.inventory_2_outlined : Icons.link_rounded,
                      ),
                      title: Text(relationship.targetLabel),
                      subtitle: Text(
                        '${relationship.kind == 'contains' ? 'Part of project' : 'Reference'} · ${relationship.targetId}',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      onTap: () => _previewNote(relationship),
                      trailing: IconButton(
                        tooltip: 'Remove relationship',
                        onPressed: () => _remove(relationship),
                        icon: const Icon(Icons.link_off_rounded),
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
        const SizedBox(height: 22),
        Text('Coming next', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        Text(
          'Tasks, calculations, files, events, repositories and conversations will attach through the same typed relationship contract.',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
      ],
    );
  }
}

class _KnowledgePickerDialog extends StatefulWidget {
  const _KnowledgePickerDialog({required this.service});
  final KnowledgeService service;

  @override
  State<_KnowledgePickerDialog> createState() => _KnowledgePickerDialogState();
}

class _KnowledgePickerDialogState extends State<_KnowledgePickerDialog> {
  final _controller = TextEditingController();
  late Future<List<KnowledgeNoteSummary>> _results;

  @override
  void initState() {
    super.initState();
    _results = widget.service.search('');
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _search() => setState(
        () => _results = widget.service.search(_controller.text.trim()),
      );

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Attach Knowledge note'),
      content: SizedBox(
        width: 620,
        height: 520,
        child: Column(
          children: [
            TextField(
              controller: _controller,
              autofocus: true,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _search(),
              decoration: InputDecoration(
                hintText: 'Search title, path, tag or content',
                prefixIcon: const Icon(Icons.search_rounded),
                suffixIcon: IconButton(
                  tooltip: 'Search',
                  onPressed: _search,
                  icon: const Icon(Icons.arrow_forward_rounded),
                ),
              ),
            ),
            const SizedBox(height: 14),
            Expanded(
              child: FutureBuilder<List<KnowledgeNoteSummary>>(
                future: _results,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) return Center(child: Text('Search failed: ${snapshot.error}'));
                  final notes = snapshot.data ?? const [];
                  if (notes.isEmpty) return const Center(child: Text('No matching notes.'));
                  return ListView.separated(
                    itemCount: notes.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (_, index) {
                      final note = notes[index];
                      return ListTile(
                        leading: const Icon(Icons.description_outlined),
                        title: Text(note.title),
                        subtitle: Text(note.path),
                        onTap: () => Navigator.pop(context, note),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
      ],
    );
  }
}

class _ProjectFormDialog extends StatefulWidget {
  const _ProjectFormDialog();

  @override
  State<_ProjectFormDialog> createState() => _ProjectFormDialogState();
}

class _ProjectFormDialogState extends State<_ProjectFormDialog> {
  final _name = TextEditingController();
  final _description = TextEditingController();
  final _tags = TextEditingController();
  String _kind = 'other';

  @override
  void dispose() {
    _name.dispose();
    _description.dispose();
    _tags.dispose();
    super.dispose();
  }

  void _submit() {
    final name = _name.text.trim();
    if (name.isEmpty) return;
    final tags = _tags.text
        .split(',')
        .map((value) => value.trim().replaceFirst(RegExp(r'^#'), ''))
        .where((value) => value.isNotEmpty)
        .toList(growable: false);
    Navigator.pop(
      context,
      _ProjectDraft(
        name: name,
        description: _description.text.trim(),
        kind: _kind,
        tags: tags,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('New project'),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _name,
                autofocus: true,
                decoration: const InputDecoration(labelText: 'Project name'),
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                initialValue: _kind,
                decoration: const InputDecoration(labelText: 'Project type'),
                items: const [
                  DropdownMenuItem(value: 'engineering', child: Text('Engineering')),
                  DropdownMenuItem(value: 'homelab', child: Text('Homelab')),
                  DropdownMenuItem(value: 'travel', child: Text('Travel')),
                  DropdownMenuItem(value: 'fitness', child: Text('Fitness')),
                  DropdownMenuItem(value: 'personal', child: Text('Personal')),
                  DropdownMenuItem(value: 'other', child: Text('Other')),
                ],
                onChanged: (value) => setState(() => _kind = value ?? 'other'),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: _description,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(labelText: 'Description'),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: _tags,
                decoration: const InputDecoration(
                  labelText: 'Tags',
                  hintText: 'stormwater, SydneyWater',
                  helperText: 'Comma separated',
                ),
                onSubmitted: (_) => _submit(),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _submit, child: const Text('Create')),
      ],
    );
  }
}

class _ProjectDraft {
  const _ProjectDraft({
    required this.name,
    required this.description,
    required this.kind,
    required this.tags,
  });

  final String name;
  final String description;
  final String kind;
  final List<String> tags;
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final icon = switch (status) {
      'active' => Icons.play_circle_outline_rounded,
      'paused' => Icons.pause_circle_outline_rounded,
      'completed' => Icons.check_circle_outline_rounded,
      'archived' => Icons.archive_outlined,
      _ => Icons.circle_outlined,
    };
    return Chip(
      avatar: Icon(icon, size: 16),
      label: Text(_statusLabel(status)),
      visualDensity: VisualDensity.compact,
    );
  }
}

class _StateCard extends StatelessWidget {
  const _StateCard({
    required this.icon,
    required this.title,
    required this.message,
    required this.actionLabel,
    required this.onAction,
  });

  final IconData icon;
  final String title;
  final String message;
  final String actionLabel;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            children: [
              Icon(icon, size: 40),
              const SizedBox(height: 12),
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 6),
              Text(message, textAlign: TextAlign.center),
              const SizedBox(height: 14),
              FilledButton.tonal(onPressed: onAction, child: Text(actionLabel)),
            ],
          ),
        ),
      );
}

IconData _kindIcon(String kind) => switch (kind) {
      'engineering' => Icons.engineering_outlined,
      'homelab' => Icons.dns_outlined,
      'travel' => Icons.flight_takeoff_rounded,
      'fitness' => Icons.fitness_center_rounded,
      'personal' => Icons.person_outline_rounded,
      _ => Icons.folder_outlined,
    };

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
