package com.example.pet_project_frontend.presentation.mypage.main

import androidx.lifecycle.ViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject

@HiltViewModel
class MyPageViewModel @Inject constructor() : ViewModel() {

    private val _uiState = MutableStateFlow(MyPageUiState())
    val uiState: StateFlow<MyPageUiState> = _uiState.asStateFlow()

    init {
        // 임시 데이터
        _uiState.value = MyPageUiState(
            petName = "레오",
            breed = "골든 리트리버",
            age = "3살",
            birthDate = "2020.09.21",
            gender = "수컷"
        )
    }
}

data class MyPageUiState(
    val petName: String = "",
    val breed: String = "",
    val age: String = "",
    val birthDate: String = "",
    val gender: String = "",
    val profileImageUrl: String? = null,
    val isLoading: Boolean = false
)