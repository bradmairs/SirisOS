import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_service.dart';

class ProjectRecord {
  const ProjectRecord({
    required this.id,
    required this.name,
    required this.description,
    required this.kind,
    required this.status,
    required this.tags,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String name;
  final String description;
  final String kind;
  final String status;
  final List<String> tags;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory ProjectRecord.fromJson(Map<String, dynamic> json) => ProjectRecord(
        id: json['id'] as String,
        name: json['name'] as String,
        description: json['description'] as String? ?? '',
        kind: json['kind'] as String? ?? 'other',
        status: json['status'] as String? ?? 'active',
        tags: (json['tags'] as List<dynamic>? ?? const [])
            .whereType<String>()
            .toList(growable: false),
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );
}

class CurrentProjectState {
  const CurrentProjectState({
    required this.project,
    this.selectedAt,
    this.provenance,
  });

  final ProjectRecord? project;
  final DateTime? selectedAt;
  final String? provenance;

  factory CurrentProjectState.fromJson(Map<String, dynamic> json) =>
      CurrentProjectState(
        project: json['project'] is Map<String, dynamic>
            ? ProjectRecord.fromJson(json['project'] as Map<String, dynamic>)
            : null,
        selectedAt: json['selected_at'] is String
            ? DateTime.tryParse(json['selected_at'] as String)
            : null,
        provenance: json['provenance'] as String?,
      );
}

class ProjectRelationship {
  const ProjectRelationship({
    required this.id,
    required this.projectId,
    required this.targetType,
    required this.targetId,
    required this.targetLabel,
    required this.kind,
    required this.provenance,
    required this.createdAt,
  });

  final String id;
  final String projectId;
  final String targetType;
  final String targetId;
  final String targetLabel;
  final String kind;
  final String provenance;
  final DateTime createdAt;

  factory ProjectRelationship.fromJson(Map<String, dynamic> json) => ProjectRelationship(
        id: json['id'] as String,
        projectId: json['project_id'] as String,
        targetType: json['target_type'] as String,
        targetId: json['target_id'] as String,
        targetLabel: json['target_label'] as String? ?? json['target_id'] as String,
        kind: json['kind'] as String? ?? 'contains',
        provenance: json['provenance'] as String? ?? 'manual',
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

class ProjectService {
  Map<String, String> get _jsonHeaders => {
        ...AuthService.authorizationHeaders,
        'Content-Type': 'application/json',
      };

  Future<List<ProjectRecord>> listProjects() async {
    final response = await http
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/projects'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw ProjectServiceException('Unable to load projects (${response.statusCode}).');
    }
    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return (json['projects'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(ProjectRecord.fromJson)
        .toList(growable: false);
  }

  Future<CurrentProjectState> currentProject() async {
    final response = await http
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/projects/current'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw ProjectServiceException('Unable to load current project (${response.statusCode}).');
    }
    return CurrentProjectState.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<CurrentProjectState> setCurrentProject(String? projectId) async {
    final response = await http
        .put(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/projects/current'),
          headers: _jsonHeaders,
          body: jsonEncode({'project_id': projectId}),
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw ProjectServiceException('Unable to set current project (${response.statusCode}).');
    }
    return CurrentProjectState.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<ProjectRecord> createProject({
    required String name,
    String description = '',
    String kind = 'other',
    List<String> tags = const [],
  }) async {
    final response = await http
        .post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/projects'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'name': name,
            'description': description,
            'kind': kind,
            'tags': tags,
          }),
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 201) {
      throw ProjectServiceException('Unable to create project (${response.statusCode}).');
    }
    return ProjectRecord.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<ProjectRecord> updateProject(
    String projectId, {
    String? name,
    String? description,
    String? kind,
    String? status,
    List<String>? tags,
  }) async {
    final payload = <String, dynamic>{};
    if (name != null) payload['name'] = name;
    if (description != null) payload['description'] = description;
    if (kind != null) payload['kind'] = kind;
    if (status != null) payload['status'] = status;
    if (tags != null) payload['tags'] = tags;
    final response = await http
        .patch(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/projects/$projectId'),
          headers: _jsonHeaders,
          body: jsonEncode(payload),
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw ProjectServiceException('Unable to update project (${response.statusCode}).');
    }
    return ProjectRecord.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<List<ProjectRelationship>> relationships(String projectId) async {
    final response = await http
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/projects/$projectId/relationships'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw ProjectServiceException('Unable to load project relationships (${response.statusCode}).');
    }
    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return (json['relationships'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(ProjectRelationship.fromJson)
        .toList(growable: false);
  }

  Future<ProjectRelationship> attachKnowledgeNote(
    String projectId,
    String notePath, {
    String kind = 'contains',
  }) async {
    final response = await http
        .post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/projects/$projectId/relationships'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'target_type': 'knowledge_note',
            'target_id': notePath,
            'kind': kind,
          }),
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 201) {
      throw ProjectServiceException('Unable to attach Knowledge note (${response.statusCode}).');
    }
    return ProjectRelationship.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<void> removeRelationship(String projectId, String relationshipId) async {
    final response = await http
        .delete(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/projects/$projectId/relationships/$relationshipId'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 204) {
      throw ProjectServiceException('Unable to remove project relationship (${response.statusCode}).');
    }
  }
}

class ProjectServiceException implements Exception {
  const ProjectServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
