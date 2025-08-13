package com.example.pet_project_frontend.presentation.mypage.main.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Divider
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.pet_project_frontend.core.theme.MyPageColors

@Composable
fun SettingsSection(
    onNotificationClick: () -> Unit,
    onVerificationClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White)
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 26.dp)
        ) {
            SettingsItemRow(
                label = "알림",
                onClick = onNotificationClick
            )

            Divider(color = MyPageColors.Background)

            SettingsItemRow(
                label = "신원 인증",
                onClick = onVerificationClick
            )
        }
    }
}
