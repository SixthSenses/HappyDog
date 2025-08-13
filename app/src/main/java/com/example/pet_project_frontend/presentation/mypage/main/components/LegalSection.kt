package com.example.pet_project_frontend.presentation.mypage.main.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Divider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pet_project_frontend.core.theme.MyPageColors

@Composable
fun LegalSection(
    onTermsClick: () -> Unit,
    onPrivacyClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 26.dp)
        ) {
            // 법적 정보 헤더
            Text(
                text = "법적 정보",
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                color = MyPageColors.Primary,
                modifier = Modifier.padding(vertical = 8.dp)
            )

            SettingsItemRow(
                label = "서비스 이용 약관",
                onClick = onTermsClick
            )

            Divider(color = MyPageColors.Background)

            SettingsItemRow(
                label = "개인정보 처리방침",
                onClick = onPrivacyClick
            )
        }
    }
}
