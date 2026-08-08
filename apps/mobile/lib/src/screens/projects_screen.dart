import 'package:flutter/material.dart';

import '../services/knowledge_service.dart';
import '../services/project_service.dart';

class ProjectsScreen extends StatefulWidget {
  const ProjectsScreen({super.key});

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen> {
  final ProjectService _projects = ProjectService();
  final KnowledgeService _knowledge = KnowledgeService();
  late Future<List<ProjectRecord>> _future;

  @override
  void initState() {
    super.initState();
    _future = _projects.list();
  }

  void _refresh() => setState(() => _future = _projects.list());

  Future<void> _createProject() async {
    final name = TextEditingController();
    var kind = 'other';
    final created = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('New project'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: name, autofocus: true, decoration: const InputDecoration(labelText: 'Project name')),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: kind,
                decoration: const InputDecoration(labelText: 'Type'),
                items: const ['engineering', 'homelab', 'travel', 'fitness', 'personal', 'other']
                    .map((value) => DropdownMenuItem(value: value, child: Text(_title(value))))
                    .toList(),
                onChanged: (value) => setDialogState(() => kind = value ?? 'other'),
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Create')),
          ],
        ),
      ),
    );
    if (created != true || name.text.trim().isEmpty) return;
    await _projects.create(name: name.text.trim(), kind: kind);
    if (mounted) _refresh();
  }

  @override
  Widget build(BuildContext context) => SafeArea(
        child: FutureBuilder<List<ProjectRecord>>(
          future: _future,
          builder: (context, snapshot) {
            final projects = snapshot.data;
            return CustomScrollView(
              slivers: [
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 22, 20, 12),
                  sliver: SliverToBoxAdapter(
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text('Projects', style: Theme.of(context).textTheme.headlineMedium),
                            const SizedBox(height: 4),
                            Text('Connect notes and context around the things you are actively working on.', style: Theme.of(context).textTheme.bodyMedium),
                          ]),
                        ),
                        IconButton.filledTonal(onPressed: _refresh, icon: const Icon(Icons.refresh_rounded), tooltip: 'Refresh'),
                        const SizedBox(width: 8),
                        FilledButton.icon(onPressed: _createProject, icon: const Icon(Icons.add_rounded), label: const Text('Project')),
                      ],
                    ),
                  ),
                ),
                if (snapshot.connectionState == ConnectionState.waiting && projects == null)
                  const SliverFillRemaining(child: Center(child: CircularProgressIndicator()))
                else if (snapshot.hasError && projects == null)
                  SliverFillRemaining(
                    child: Center(child: Padding(padding: const EdgeInsets.all(24), child: Text('Projects are unavailable: ${snapshot.error}'))),
                  )
                else if (projects!.isEmpty)
                  const SliverFillRemaining(
                    child: Center(child: Padding(padding: EdgeInsets.all(28), child: Text('No projects yet. Create one to start grouping Knowledge notes and future SirisOS context.'))),
                  )
                else
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
                    sliver: SliverList.separated(
                      itemCount: projects.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (context, index) {
                        final project = projects[index];
                        return Card(
                          child: ListTile(
                            leading: CircleAvatar(child: Icon(_kindIcon(project.kind))),
                            title: Text(project.name),
                            subtitle: Text('${_title(project.kind)} · ${_title(project.status)}${project.description.isEmpty ? '' : '\n${project.description}'}'),
                            isThreeLine: project.description.isNotEmpty,
                            trailing: const Icon(Icons.chevron_right_rounded),
                            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => _ProjectDetailScreen(project: project, projects: _projects, knowledge: _knowledge))),
                          ),
                        );
                      },
                    ),
                  ),
              ],
            );
          },
        ),
      );
}

class _ProjectDetailScreen extends StatefulWidget {
  const _ProjectDetailScreen({required this.project, required this.projects, required this.knowledge});
  final ProjectRecord project;
  final ProjectService projects;
  final KnowledgeService knowledge;

  @override
  State<_ProjectDetailScreen> createState() => _ProjectDetailScreenState();
}

class _ProjectDetailScreenState extends State<_ProjectDetailScreen> {
  late Future<List<ProjectRelationship>> _relationships;

  @override
  void initState() {
    super.initState();
    _relationships = widget.projects.relationships(widget.project.id);
  }

  void _refresh() => setState(() => _relationships = widget.projects.relationships(widget.project.id));

  Future<void> _attachNote() async {
    final notes = await widget.knowledge.browse();
    if (!mounted) return;
    final selected = await showDialog<KnowledgeNoteSummary>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Attach Knowledge note'),
        content: SizedBox(
          width: 520,
          height: 420,
          child: notes.notes.isEmpty
              ? const Center(child: Text('No Knowledge notes are available.'))
              : ListView.builder(
                  itemCount: notes.notes.length,
                  itemBuilder: (context, index) {
                    final note = notes.notes[index];
                    return ListTile(
                      leading: const Icon(Icons.description_outlined),
                      title: Text(note.title),
                      subtitle: Text(note.path),
                      onTap: () => Navigator.pop(context, note),
                    );
                  },
                ),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel'))],
      ),
    );
    if (selected == null) return;
    try {
      await widget.projects.attachKnowledge(widget.project.id, selected.path);
      if (mounted) _refresh();
    } catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$error')));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(widget.project.name)),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Wrap(spacing: 8, runSpacing: 8, children: [
              Chip(avatar: Icon(_kindIcon(widget.project.kind), size: 18), label: Text(_title(widget.project.kind))),
              Chip(label: Text(_title(widget.project.status))),
              ...widget.project.tags.map((tag) => Chip(label: Text('#$tag'))),
            ]),
            if (widget.project.description.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(widget.project.description),
            ],
            const SizedBox(height: 24),
            Row(children: [
              Expanded(child: Text('Knowledge', style: Theme.of(context).textTheme.titleLarge)),
              FilledButton.tonalIcon(onPressed: _attachNote, icon: const Icon(Icons.add_link_rounded), label: const Text('Attach note')),
            ]),
            const SizedBox(height: 8),
            FutureBuilder<List<ProjectRelationship>>(
              future: _relationships,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting && snapshot.data == null) {
                  return const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()));
                }
                if (snapshot.hasError) return Text('Unable to load relationships: ${snapshot.error}');
                final relationships = snapshot.data ?? const [];
                if (relationships.isEmpty) return const Card(child: Padding(padding: EdgeInsets.all(18), child: Text('No Knowledge notes attached yet.')));
                return Column(
                  children: relationships.map((relationship) => Card(
                    child: ListTile(
                      leading: const Icon(Icons.menu_book_outlined),
                      title: Text(relationship.targetLabel),
                      subtitle: Text('${relationship.kind} · ${relationship.targetId}'),
                      trailing: IconButton(
                        tooltip: 'Remove relationship',
                        icon: const Icon(Icons.link_off_rounded),
                        onPressed: () async {
                          await widget.projects.removeRelationship(widget.project.id, relationship.id);
                          if (mounted) _refresh();
                        },
                      ),
                    ),
                  )).toList(growable: false),
                );
              },
            ),
          ],
        ),
      );
}

String _title(String value) => value.isEmpty ? value : '${value[0].toUpperCase()}${value.substring(1)}';

IconData _kindIcon(String kind) => switch (kind) {
      'engineering' => Icons.engineering_outlined,
      'homelab' => Icons.dns_outlined,
      'travel' => Icons.flight_outlined,
      'fitness' => Icons.fitness_center_outlined,
      'personal' => Icons.person_outline_rounded,
      _ => Icons.folder_outlined,
    };
