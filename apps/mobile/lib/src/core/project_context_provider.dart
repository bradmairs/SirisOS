import '../services/project_service.dart';
import 'siris_context_service.dart';

class ProjectContextProvider implements SirisContextProvider {
  ProjectContextProvider({ProjectService? service}) : _service = service ?? ProjectService();

  final ProjectService _service;

  @override
  String get id => 'projects.current';

  @override
  Future<List<SirisContextFact>> collect() async {
    final state = await _service.currentProject();
    final project = state.project;
    if (project == null) return const [];
    return [factFor(project)];
  }

  static SirisContextFact factFor(ProjectRecord project) => SirisContextFact(
        id: 'project.current.${project.id}',
        label: 'Project: ${project.name}',
        domain: domainFor(project.kind),
        priority: 55,
        source: 'projects.manual_selection',
        detail: '${_kindLabel(project.kind)} project · ${project.status}',
      );

  static SirisContextDomain domainFor(String kind) => switch (kind) {
        'engineering' => SirisContextDomain.engineering,
        'homelab' => SirisContextDomain.homelab,
        _ => SirisContextDomain.personal,
      };

  static String _kindLabel(String kind) => switch (kind) {
        'engineering' => 'Engineering',
        'homelab' => 'Homelab',
        'travel' => 'Travel',
        'fitness' => 'Fitness',
        'personal' => 'Personal',
        _ => 'Other',
      };
}
