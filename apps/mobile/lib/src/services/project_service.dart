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
        tags: (json['tags'] as List<dynamic>? ?? const []).whereType<String>().toList(growable: false),
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
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
  });

  final String id;
  final String projectId;
  final String targetType;
  final String targetId;
  final String targetLabel;
  final String kind;
  final String provenance;

  factory ProjectRelationship.fromJson(Map<String, dynamic> json) => ProjectRelationship(
        id: json['id'] as String,
        projectId: json['project_id'] as String,
        targetType: json['target_type'] as String,
        targetId: json['target_id'] as String,
        targetLabel: json['target_label'] as String? ?? json['target_id'] as String,
        kind: json['kind'] as String,
        provenance: json['provenance'] as String? ?? 'manual',
      );
}

class ProjectService {
  Future<List<ProjectRecord>> list() async {
    final response = await http
        .get(Uri.parse('${ApiConfig.baseUrl}/api/v1/projects'), headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) throw ProjectServiceException('Unable to load projects (${response.statusCode}).');
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return (body['projects'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(ProjectRecord.fromJson)
        .toList(growable: false);
  }

  Future<ProjectRecord> create({required String name, required String kind}) async {
    final response = await http
        .post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/projects'),
          headers: {...AuthService.authorizationHeaders, 'Content-Type': 'application/json'},
          body: jsonEncode({'name': name, 'kind': kind}),
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 201) throw ProjectServiceException('Unable to create project (${response.statusCode}).');
    return ProjectRecord.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<List<ProjectRelationship>> relationships(String projectId) async {
    final response = await http
        .get(Uri.parse('${ApiConfig.baseUrl}/api/v1/projects/$projectId/relationships'), headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) throw ProjectServiceException('Unable to load project relationships (${response.statusCode}).');
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return (body['relationships'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(ProjectRelationship.fromJson)
        .toList(growable: false);
  }

  Future<ProjectRelationship> attachKnowledge(String projectId, String notePath) async {
    final response = await http
        .post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/projects/$projectId/relationships'),
          headers: {...AuthService.authorizationHeaders, 'Content-Type': 'application/json'},
          body: jsonEncode({'target_type': 'knowledge_note', 'target_id': notePath, 'kind': 'contains'}),
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 201) throw ProjectServiceException('Unable to attach note (${response.statusCode}).');
    return ProjectRelationship.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<void> removeRelationship(String projectId, String relationshipId) async {
    final response = await http
        .delete(Uri.parse('${ApiConfig.baseUrl}/api/v1/projects/$projectId/relationships/$relationshipId'), headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 204) throw ProjectServiceException('Unable to remove relationship (${response.statusCode}).');
  }
}

class ProjectServiceException implements Exception {
  const ProjectServiceException(this.message);
  final String message;
  @override
  String toString() => message;
}
