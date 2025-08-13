package com.example.pet_project_frontend.presentation.mypage.main.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.example.pet_project_frontend.core.theme.MyPageColors

@Composable
fun ProfileHeader(
    name: String,
    description: String,
    profileImageUrl: String? = null,
    onProfileImageClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 24.dp, vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 프로필 이미지 영역
        Box {
            Box(
                modifier = Modifier
                    .size(59.dp)
                    .clip(CircleShape)
                    .background(MyPageColors.Primary)
                    .clickable { onProfileImageClick() }
            ) {
                profileImageUrl?.let {
                    AsyncImage(
                        model = it,
                        contentDescription = "프로필 사진",
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop
                    )
                }
            }

            // 더하기 버튼
            Box(
                modifier = Modifier
                    .size(19.dp)
                    .align(Alignment.BottomEnd)
                    .clip(CircleShape)
                    .background(MyPageColors.ProfileAddButton)
                    .clickable { onProfileImageClick() },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Add,
                    contentDescription = "프로필 사진 추가",
                    modifier = Modifier.size(15.dp),
                    tint = MyPageColors.Primary
                )
            }
        }

        Spacer(modifier = Modifier.width(18.dp))

        // 텍스트 정보
        Column {
            Text(
                text = name,
                fontSize = 22.sp,
                fontWeight = FontWeight.SemiBold,
                color = MyPageColors.Primary,
                letterSpacing = (-0.025).sp
            )

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = description,
                fontSize = 16.sp,
                fontWeight = FontWeight.Medium,
                color = MyPageColors.Tertiary,
                letterSpacing = (-0.01).sp
            )
        }
    }
    }