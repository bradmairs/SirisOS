import 'package:flutter/material.dart';

import 'siris_agent_chat_screen.dart';
import 'siris_memory_screen.dart';

class SirisHubScreen extends StatelessWidget {
  const SirisHubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const DefaultTabController(
      length: 2,
      child: Column(
        children: [
          Material(
            child: TabBar(
              tabs: [
                Tab(icon: Icon(Icons.chat_bubble_outline_rounded), text: 'Chat'),
                Tab(icon: Icon(Icons.psychology_alt_outlined), text: 'Memory'),
              ],
            ),
          ),
          Expanded(
            child: TabBarView(
              children: [
                SirisAgentChatScreen(),
                SirisMemoryScreen(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
