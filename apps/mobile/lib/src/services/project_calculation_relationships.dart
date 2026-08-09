import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_service.dart';
import 'project_service.dart';

extension ProjectCalculationRelationships on ProjectService {
  Future<ProjectRelationship> attachCalculation(
    String projectId,
    String calculationId, {
    String kind = 'contains',
  }) async {
    final response = await http
        .post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/projects/$projectId/relationships'),
          headers: {
            ...AuthService.authorizationHeaders,
            'Content-Type': 'application/json',
          },
          body: jsonEncode({
            'target_type': 'calculation',
            'target_id': calculationId,
            'kind': kind,
          }),
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 201) {
      String detail = 'Unable to attach calculation (${response.statusCode}).';
      try {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        if (decoded['detail'] is String) detail = decoded['detail'] as String;
      } catch (_) {}
      throw ProjectServiceException(detail);
    }
    return ProjectRelationship.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }
}
