package com.example.pet_project_frontend.presentation.mypage.main

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.pet_project_frontend.core.theme.MyPageColors
import com.example.pet_project_frontend.core.navigation.BottomNavigation
import com.example.pet_project_frontend.presentation.mypage.main.components.ProfileHeader
import com.example.pet_project_frontend.presentation.mypage.main.components.ProfileInfoSection
import com.example.pet_project_frontend.presentation.mypage.main.components.SettingsSection
import com.example.pet_project_frontend.presentation.mypage.main.components.LegalSection
import com.example.pet_project_frontend.presentation.mypage.main.components.WithdrawalSection
import com.example.pet_project_frontend.presentation.mypage.main.components.AppVersionSection

@Composable
fun MyPageScreen(
    onNameClick: () -> Unit = {},
    onBirthdateClick: () -> Unit = {},
    onGenderClick: () -> Unit = {},
    onBreedClick: () -> Unit = {},
    onNotificationClick: () -> Unit = {},
    onVerificationClick: () -> Unit = {},
    onTermsClick: () -> Unit = {},
    onPrivacyClick: () -> Unit = {},
    onWithdrawClick: () -> Unit = {},
    onProfileImageClick: () -> Unit = {},
    viewModel: MyPageViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val scrollState = rememberScrollState()

    Scaffold(
        bottomBar = {
            BottomNavigation(currentRoute = "mypage")
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(MyPageColors.Background)
                .padding(paddingValues)
                .verticalScroll(scrollState)
        ) {
            // 프로필 헤더
            ProfileHeader(
                name = uiState.petName,
                description = "${uiState.breed} · ${uiState.age}",
                profileImageUrl = uiState.profileImageUrl,
                onProfileImageClick = onProfileImageClick
            )

            Spacer(modifier = Modifier.height(12.dp))

            // 프로필 정보 섹션
            ProfileInfoSection(
                name = uiState.petName,
                birthDate = uiState.birthDate,
                gender = uiState.gender,
                breed = uiState.breed,
                onNameClick = onNameClick,
                onBirthdateClick = onBirthdateClick,
                onGenderClick = onGenderClick,
                onBreedClick = onBreedClick
            )

            Spacer(modifier = Modifier.height(12.dp))

            SettingsSection(
                onNotificationClick = onNotificationClick,
                onVerificationClick = onVerificationClick
            )

            Spacer(modifier = Modifier.height(12.dp))

            // 법적 정보 카드
            LegalSection(
                onTermsClick = onTermsClick,
                onPrivacyClick = onPrivacyClick
            )

            Spacer(modifier = Modifier.height(12.dp))

            // 탈퇴하기 카드
            WithdrawalSection(onClick = onWithdrawClick)

            Spacer(modifier = Modifier.height(32.dp))

            // 앱 버전
            AppVersionSection()

            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

