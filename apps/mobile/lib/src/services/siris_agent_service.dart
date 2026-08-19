import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/siris_agent.dart';
import 'auth_service.dart';

class SirisAgentService {
  Future<SirisAgentReply> ask(List<SirisAgentMessage> messages) async {
    final response = await http.post(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/siris/agent/ask'),
      headers: {
        ...AuthService.authorizationHeaders,
        'Content-Type': 'application/json',
      },
      body: jsonEncode({'messages': messages.map((item) => item.toJson()).toList()}),
    );
    if (response.statusCode != 200) {
      final decoded = jsonDecode(response.body.isEmpty ? '{}' : response.body);
      throw Exception(decoded is Map<String, dynamic>
          ? decoded['detail'] ?? 'Could not reach Siris.'
          : 'Could not reach Siris.');
    }
    return SirisAgentReply.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }
}
